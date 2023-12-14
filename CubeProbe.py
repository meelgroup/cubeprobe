from __future__ import print_function
import sys
import os
import math
import random
import argparse
import tempfile
import copy
import time
import threading

from numpy.random import exponential as _exp

SAMPLER_QUICKSAMPLER = 1
SAMPLER_STS = 2
SAMPLER_CMS = 3


def parseWeights(inputFile, indVarList):
    f = open(inputFile, "r")
    lines = f.readlines()
    f.close()
    weight_map = {}

    for line in lines:
        if line.startswith("w"):
            variable, weight = line[2:].strip().split()
            variable = int(variable)
            weight = float(weight)
            if (0.0 < weight < 1.0):
                if (variable in indVarList):
                    weight_map[variable] = weight
            else:
                print("Error: Weights should only be in (0,1) ")
                exit(-1)
    return weight_map


def parseIndSupport(indSupportFile):  # returns List of Independent Variables
    f = open(indSupportFile, "r")
    lines = f.readlines()
    f.close()
    indList = []
    numVars = 0
    for line in lines:
        if line.startswith("p cnf"):
            fields = line.split()
            numVars = int(fields[2])
        if line.startswith("c ind"):
            indList.extend(
                line.strip()
                .replace("c ind", "")
                .replace(" 0", "")
                .strip()
                .replace("v ", "")
                .split()
            )
    if len(indList) == 0:
        indList = [int(x) for x in range(1, numVars + 1)]
    else:
        indList = [int(x) for x in indList]
    return indList



def getSolutionFromCMSsampler(inputFile, numSolutions, indVarList, newSeed):
    
    tempOutputFile = inputFile + ".txt"

    cmd = "./samplers/cmsgen --samples " + str(numSolutions) + " -s " + str(newSeed)
    cmd += " --samplefile " + tempOutputFile + " " + inputFile + " > /dev/null 2>&1"

    os.system(cmd)

    with open(tempOutputFile, 'r') as f:
        lines = f.readlines()

    solList = []
    for line in lines:
        if line.strip() == 'SAT':
            continue

        sol = []
        lits = line.split(" ")
        for y in indVarList:
            if str(y) in lits:
                sol.append(y)

            if "-" + str(y) in lits:
                sol.append(-y)
        solList.append(sol)

    solreturnList = solList
    if len(solList) > numSolutions:
        solreturnList = random.sample(solList, numSolutions)
    if len(solList) < numSolutions:
        print("cryptominisat5 Did not find required number of solutions")
        sys.exit(1)
    os.unlink(tempOutputFile)
    return solreturnList



def getSolutionFromSampler(inputFile, numSolutions, samplerType, indVarList, seed, thread, outfp):

    if samplerType == SAMPLER_QUICKSAMPLER:
        return getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed, thread, outfp)
    if samplerType == SAMPLER_STS:
        return getSolutionFromSTS(seed, inputFile, numSolutions, indVarList)
    if samplerType == SAMPLER_CMS:
        return getSolutionFromCMSsampler(inputFile, numSolutions, indVarList, seed)
    else:
        print("Error")
        return None


def getSolutionFromSTS(seed, inputFile, numSolutions, indVarList):
    kValue = 50
    samplingRounds = int(numSolutions/kValue) + 1
    inputFileSuffix = inputFile.split('/')[-1][:-4]
    outputFile = tempfile.gettempdir()+'/'+inputFileSuffix+"sts.out"    
    solList = []
    while True:
        cmd = './samplers/STSnew -k='+str(kValue)+' -nsamples='+str(samplingRounds)+' -rnd-seed=' + str(seed) +' '+str(inputFile)
        cmd += ' > '+str(outputFile)
        os.system(cmd)

        with open(outputFile, 'r') as f:
            lines = f.readlines()
            
        shouldStart = False
        for j in range(len(lines)):
            if(lines[j].strip() == 'Outputting samples:' or lines[j].strip() == 'start'):
                shouldStart = True
                continue
            if (lines[j].strip().startswith('Log') or lines[j].strip() == 'end'):
                shouldStart = False
            if (shouldStart):
                i = 0
                sol = []
                line = lines[j].strip().split(',')
                for x in indVarList: 
                    if (line[x-1] == '0'):
                        sol.append(-1*x)
                    else:
                        sol.append(x)
                    i += 1
                solList.append(sol)
                
        solreturnList = solList
        if len(solList) > numSolutions:
            solreturnList = random.sample(solList, numSolutions)
            break
    os.unlink(outputFile)
    return solreturnList



def getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed, thread, outfp):
    solreturnList = []
    while True:
        cmd = (
            "./samplers/quicksampler" +" -n "
            + str(numSolutions * 5)
            + " "
            + str(inputFile)
            + " > /dev/null 2>&1"
            )
        os.system(cmd)
        cmd = "./samplers/z3"+" " + str(inputFile) + " > /dev/null 2>&1"
        os.system(cmd)
        i = 0
        if numSolutions > 1:
            i = 0

        f = open(inputFile + ".samples", "r")
        lines = f.readlines()
        f.close()
        f = open(inputFile + ".samples.valid", "r")
        validLines = f.readlines()
        f.close()
        solList = []
        for j in range(len(lines)):
            if validLines[j].strip() == "0":
                continue
            fields = lines[j].strip().split(":")
            sol = []
            i = 0
            for x in list(fields[1].strip()):
                if x == "0":
                    sol.append(-1*indVarList[i])
                else:  
                    sol.append(indVarList[i])
                i += 1
            solList.append(sol)

        solreturnList += solList
        if len(solreturnList) > numSolutions:
            solreturnList = random.sample(solreturnList, numSolutions) 
            break
    
    os.unlink(inputFile+'.samples')
    os.unlink(inputFile+'.samples.valid')

    return solreturnList


def constructNewFile(tempFile, var, indVarList):
    
    f = open(tempFile, "r")
    lines = f.readlines()
    f.close()
    
    #---------------------------Old formula--------------------------#
    oldClauseStr = ""
    for line in lines:
        if line.strip().startswith("p cnf"):
            numVar = int(line.strip().split()[2])
            numClause = int(line.strip().split()[3]) + 1
        else:
            if line.strip().startswith("w"):
                oldClauseStr += line.strip()+"\n"
            elif not (line.strip().startswith("c")):
                oldClauseStr += line.strip()+"\n"


    #----------------Adding constraints-------------------#
    solClause = ""
    solClause += str(var) + ' 0\n'
    
    #----------------------construct formula-----------------------------#
    indStr = "c ind "
    indIter = 1
    for i in indVarList:
        if indIter % 10 == 0:
            indStr += " 0\nc ind "
        indStr += str(i) + " "
        indIter += 1
    indStr += " 0\n"

    headStr = "p cnf " + str(numVar) + " " + str(numClause) + "\n"
    writeStr = headStr + indStr
    writeStr += solClause
    writeStr += oldClauseStr

    f = open(tempFile, "w")
    f.write(writeStr)
    f.close()
    return indVarList


def addClique(inputFile, indVarList, newFile):
    f = open(inputFile, "r")
    lines = f.readlines()
    f.close()
    
    #---------------------Old Clause---------------------#
    oldClauseStr = ""
    for line in lines:
        if line.strip().startswith("p cnf"):
            numVar = int(line.strip().split()[2])
            numClause = int(line.strip().split()[3])
        else:
            if line.strip().startswith("w"):
                oldClauseStr += line.strip()+"\n"
            elif not (line.strip().startswith("c")):
                oldClauseStr += line.strip()+"\n"
    indStr = "c ind "
    indIter = 1
    for i in indVarList:
        if indIter % 10 == 0:
            indStr += " 0\nc ind "
        indStr += str(i) + " "
        indIter += 1
    indStr += " 0\n"

    numVarOrig = numVar
    newClause = ""
    varCount = 1
    newVar = []
    fmt = open("empty.cnf", "r")
    mtlines = fmt.readlines()
    fmt.close()
    
    for line in mtlines:
        if line.strip().startswith("p cnf"):
            newnumVar = int(line.strip().split()[2])
            newnumClause = int(line.strip().split()[3])
        else:
            if line.strip().startswith("w"):
                newClause += line.strip()+"\n"
            elif not (line.strip().startswith("c")):
                newVarbuf = [int(_var) for _var in line.strip().split()]
                for _var in newVarbuf:
                    if _var > 0:
                        newClause += str(abs(_var) + numVar) + ' '
                    elif _var < 0:
                        newClause += str( -1 * (abs(_var) + numVar)) + ' '
                    newVar.append(abs(_var) + numVar)
                newClause += '0\n' 
    
    #------------------------------------------------------------------------------#
    newVar = set(newVar)
    newVar.remove(numVar)
    newVar = sorted(list(newVar))
    indStr += "c ind "
    indIter = 1
    for i in newVar:
        if indIter % 10 == 0:
            indStr += " 0\nc ind "
        indStr += str(i) + " "
        indIter += 1
    indStr += " 0\n"

    headStr = "p cnf " + str(numVar + newnumVar) + " " + str(numClause + newnumClause) + "\n"
    writeStr = headStr + indStr
    writeStr += oldClauseStr
    writeStr += newClause
    
    f = open(newFile, "w")
    f.write(writeStr)
    f.close()

    return indVarList + newVar


def gbas(x, ith, indVarList, tempfile, samplerType, seed, k, outfp, thread):
    s, r = 0, 0
    k_ = int(k)
    k = k_
    cut_thresh = 40
    nloops = 0
    totsamples = 0
    while s < k:
        nloops += 1
        sampSet = getSolutionFromSampler(tempfile, k_, samplerType, indVarList, seed, thread, outfp)
        totsamples += k_
        for samp in sampSet:
            assert abs(samp[ith]) == abs(x[ith])
            if not (samp[ith] > 0) ^ (x[ith] > 0): 
                s += 1
            r += _exp(1)
        seed += 1
        k_ = k - s
        if nloops > cut_thresh:
            outfp.write("\texiting with current heads : " + str(s) + " out of " + str(k)+ " | exp rv: " + str(r) + "\n")
            outfp.flush()
            break

    return (k - 1) / r, totsamples
    
def estimate(x, dim, indVarList, tempFile, samplerType, seed, k, outfp, threadid):
    n = dim
    est = 1  
    totsamples = 0
    start_time = time.time()
    out, nsamples = gbas(x, 0, indVarList, tempFile, samplerType, seed, k, outfp, threadid); out = min(1, out)
    est *= out
    totsamples += nsamples
    end_time = time.time()
    outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(0) + " of " + str(n) + " : " + str(est) + "  | time taken : " + str(end_time - start_time))
    outfp.flush()
    indVarList = constructNewFile(tempFile, x[0], indVarList)
    for i in range(1, n):
        start_time = time.time()
        out, nsamples= gbas(x, i, indVarList, tempFile, samplerType, seed, k, outfp, threadid); out = min(1, out)
        est *= out
        totsamples += nsamples
        end_time = time.time()
        outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(i) + " of " + str(n) + " : " + str(out) + "  | time taken : " + str(end_time - start_time))
        outfp.flush()
        indVarList = constructNewFile(tempFile, x[i], indVarList)
    outfp.write("\n Thread " + str(threadid) + " nsolns: " + str(totsamples))
    outfp.flush()
    return est, totsamples



def inthread(sampleSet, dim, indVarList, inputFile, samplerType, seed, k, out, est, nsamp, threadid):
    print("starting Thread-", threadid)
    tempFile_th= "thread_" + str(threadid) + "_" + inputFile
    cmd = "cp " + inputFile + " ./" + tempFile_th 
    for x in sampleSet:
        os.system(cmd)
        estimates, nsamples = estimate(x, dim, indVarList, tempFile_th, samplerType, seed, k, out, threadid)
        est.append(estimates)
        nsamp.append(nsamples)
    try:
        os.unlink(tempFile_th)
    except FileNotFoundError:
        pass
    


def CubeProbe():

    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zeta", type=float, help="default = 0.3", default=0.3, dest="zeta"
    )
    parser.add_argument(
        "--eta", type=float, help="default = 0.605", default=0.605, dest="eta"
    )
    parser.add_argument(
        "--epsilon", type=float, help="default = 0.005", default=0.005, dest="epsilon"
    )
    parser.add_argument(
        "--delta", type=float, help="default = 0.2", default=0.2, dest="delta"
    )
    parser.add_argument(
        "--sampler",
        type=int,
        help=str(SAMPLER_QUICKSAMPLER)
        + " for QuickSampler;\n"
        + str(SAMPLER_STS)
        + " for STS;\n"
        + str(SAMPLER_CMS)
        + " for CMSGen;\n",
        default=SAMPLER_QUICKSAMPLER,
        dest="samplertype",
    )
    parser.add_argument("--seed", type=int, dest="seed", default=420)
    parser.add_argument("--thread", type=int, help="default use thread", default=20, dest="thread")
    parser.add_argument("--mode", help="select 'test' for tester and 'est' for estimator", default='est', dest="mode")
    parser.add_argument("input", help="input file")
    parser.add_argument("output", help="output file")
    
    args = parser.parse_args()

    if args.mode == 'test':
        print("Running in tester mode ...")
    elif args.mode == 'est':
        print("Running in estimator mode ...")

    samplerType = args.samplertype
    
    UserInputFile = args.input
    UserIndVarList = parseIndSupport(UserInputFile)

    # Current Working File
    inputFilePrefix = "sampler_" + str(samplerType) + "_" + UserInputFile.split("/")[-1][:-4]
    inputFile = inputFilePrefix + ".cnf"
    indVarList = addClique(UserInputFile, UserIndVarList, inputFile)
    
    # get the model count
    mcFile = inputFilePrefix + ".mc"
    cmd = "./samplers/approxmc " + UserInputFile + " > "  + mcFile
    os.system(cmd)

    with open(mcFile) as fp:
        lines = fp.readlines()

    mc = 0
    for line in lines:
        if line.strip().startswith('s mc') :
            mc = line.strip().split(' ')[-1]
    mc = int(mc)
    os.unlink(mcFile)

    # set up the parameters
    isthread = args.thread
    zeta = args.zeta
    eta = args.eta
    epsilon = args.epsilon
    delta = args.delta
    outputFile = args.output
    seed = args.seed
    random.seed(seed)
    if args.mode == 'test':
        zeta = (eta - epsilon) / 2

    tempFile = inputFile.split(".")[0] + "_t.cnf"

    samplerString = ""

    if samplerType == SAMPLER_QUICKSAMPLER:
        samplerString = "QuickSampler"
    if samplerType == SAMPLER_STS:
        samplerString = "STS"
    if samplerType == SAMPLER_CMS:
        samplerString = "CMSGen"

    
    #----------------------------------------- parameter calculation----------------------------------------------
    n = len(UserIndVarList) 
    numSolutions = math.ceil(2 / (zeta ** 2) * math.log(4 / delta)) 
    delta_m = delta / (2 * numSolutions)
    K = (epsilon + eta) / 2
    gamma = zeta / (1 + zeta)
    epsilon_ = gamma / 1.107
    k = math.ceil(2 * n / epsilon_**2 * (1 /( 1 - 4 / 3 * epsilon_ / math.sqrt(n))) * math.log(2 * n / delta_m))
    # print(k, numSolutions, n, epsilon_)
    #--------------------------------------------------------------------------------------------------------------
    
    f = open(outputFile, "w")
    f.write("numSolutions: "+ str(numSolutions)+ " k : " + str(k)  + "\n" + str(n) + " " + str(numSolutions) + " " + str(epsilon / math.sqrt(n)) + " " + str(delta_m / n) + "\n")
    f.flush()
    f.close()
    
    #---------------------------------------------main begins---------------------------------------
    
    # cmd = "approxmc " + UserInputFile
    # os.system(cmd)
    sampleSet = []
    sampleSet = getSolutionFromSampler(inputFile, numSolutions, samplerType, indVarList, seed, 1, f)

    dim = len(UserIndVarList)

    val = 0; nsamp = 0
    out = open(outputFile, "a")
    # print(UserIndVarList, indVarList)
    
    if isthread > 0:
        
        t = []          
        ncores = isthread  

        eachthread = [numSolutions // ncores for i in range(ncores)]
        rem = numSolutions % ncores
        for i in range(ncores):
            eachthread[i] += 1
            rem -= 1
            if rem == 0 : break
        for i in range(1, ncores):
            eachthread[i] += eachthread[i-1]

        massarray = []; nsamplesarray = []

        eachthread = [0] + eachthread
        
        for i in range(1, ncores+1):
            t.append(threading.Thread(target=inthread, args=(sampleSet[eachthread[i-1]: eachthread[i]], dim, indVarList, inputFile, samplerType, seed, k, out, massarray, nsamplesarray, i)))
        
        for i in range(ncores):
            t[i].start()
        for i in range(ncores):
            t[i].join()

        out.write("\n estimated weights : " + str(massarray) + "\n")
        out.flush()

        for est in massarray:
            try:
                val += max(0, 1 - 1 /(est * mc))
            except ZeroDivisionError:
                pass
        for ns in nsamplesarray:
            nsamp += ns
        
    else:

        val = 0
        count = 0
    
        for x in sampleSet:
            out.write(str(count) + " of " + str(len(sampleSet)) + "\t")
            out.flush()
            est, ns = estimate(x, dim, indVarList, inputFile, samplerType, seed, k, out, 1)
            val = val + max(0, 1 - 1 / (est * mc) )
            nsamp += ns
            count += 1

    out.write("\n dTV estimated : " + str(val / numSolutions))

    out.write("\n nsamples : " + str(nsamp))

    os.unlink(inputFile)

    if args.mode == 'test':
        if val / numSolutions > K:
            out.write("\n REJECTED")
            out.close()
            return 'REJECT'
        else:
            out.write("\n ACCEPTED")
            out.close()
            return 'ACCEPT'
    elif args.mode == 'est':
        return str(val / numSolutions)
    

if __name__ == "__main__":
    output = CubeProbe()
    print("output:", output)