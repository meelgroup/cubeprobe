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
SAMPLER_SPUR = 4
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


def getSolutionFromSpur(seed, inputFile, numSolutions, indVarList):
    # inputFileSuffix = inputFile.split('/')[-1][:-4]
    # tempOutputFile = inputFile + ".txt"
    inputFileSuffix = inputFile.split('/')[-1][:-4]
    tempOutputFile = tempfile.gettempdir()+'/'+inputFileSuffix+"spur.out"
    cmd = './samplers/spur -seed %d -s %d -out %s -cnf %s' % (
        seed, numSolutions, tempOutputFile, inputFile)
    # if args.verbose:
    print("cmd: ", cmd)
    os.system(cmd)

    with open(tempOutputFile, 'r') as f:
        lines = f.readlines()

    solList = []
    startParse = False
    for line in lines:
        if (line.startswith('#START_SAMPLES')):
            startParse = True
            continue
        if (not(startParse)):
            continue
        if (line.startswith('#END_SAMPLES')):
            startParse = False
            continue
        if (line.startswith('UNSAT')):
            print("UNSAT")
            return -1

        fields = line.strip().split(',')
        solCount = int(fields[0])
        sol = []
        i = 1
        # print(fields)
        for x in list(fields[1]):
            if i in indVarList:
                if (x == '0'):
                    sol.append(-i)
                else:
                    sol.append(i)
            i += 1
        for i in range(solCount):
            solList.append(sol)

    os.unlink(tempOutputFile)
    return solList



def getSolutionFromCMSsampler(inputFile, numSolutions, indVarList, newSeed):
    # inputFileSuffix = inputFile.split('/')[-1][:-4]
    # outputFile = tempfile.gettempdir()+'/'+inputFileSuffix+".out"
    tempOutputFile = inputFile + ".txt"

    # cmd = "./samplers/cryptominisat5 --restart fixed --maple 0 --verb 0 --nobansol"
    # cmd += " --scc 1 -n 1 --presimp 0 --polar rnd --freq 0.9999 --fixedconfl 100"
    # cmd += " --random " + str(newSeed) + " --maxsol " + str(numSolutions)
    # cmd += " --dumpresult " + tempOutputFile
    # cmd += " " + inputFile + " > /dev/null 2>&1"

    cmd = "cmsgen --samples " + str(numSolutions) + " -s " + str(newSeed)
    cmd += " --samplefile " + tempOutputFile + " " + inputFile + " > /dev/null 2>&1"

    # if args.verbose:
    #     print("cmd: ", cmd)
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
    if samplerType == SAMPLER_SPUR:
        return getSolutionFromSpur(seed, inputFile, numSolutions, indVarList)
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
        #if args.verbose:
        #    print("cmd: ", cmd)
        # print(cmd)
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
                # valutions are 0 and 1 and in the same order as c ind.
                # for x in list(lines[j].strip()):
                #     if (x == '0'):
                #         sol.append(-1*indVarList[i])
                #     else:
                #         sol.append(indVarList[i])
                #     i += 1
                # solList.append(sol)
                line = lines[j].strip().split(',')
                for x in indVarList: 
                    if (line[x-1] == '0'):
                        sol.append(-1*x)
                    else:
                        sol.append(x)
                    i += 1
                solList.append(sol)
                
        solreturnList = solList
        # print(solList)
        if len(solList) > numSolutions:
            solreturnList = random.sample(solList, numSolutions)
            break
        seed += 1
        # elif len(solList) < numSolutions:
        #     print(len(solList), numSolutions)
        #     # print(solList)
        #     print("STS Did not find required number of solutions")
        #     # sys.exit(1)
        #     # kValue = int(kValue / 5) + 1
    # print("break+++============")
    os.unlink(outputFile)
    return solreturnList



def getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed, thread, outfp):
    # cmd ='approxmc -v 0 ' + inputFile + ' > checkherethenumber'
    # os.system(cmd)
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
        # print("lines:", len(lines), inputFile)
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
                # if i >= len(indVarList) : break
            solList.append(sol)

        solreturnList += solList
        if len(solreturnList) > numSolutions:
            solreturnList = random.sample(solreturnList, numSolutions) 
            break
        elif len(solreturnList) < numSolutions:
            print(str(thread) + " " + str(len(solList)) + " " + str(numSolutions))
        seed += 1
        #     outfp.write(str(thread) + str(len(solList)) + str(numSolutions))
        #     outfp.flush()
        #     # print(solList[0])
        #     outfp.write(str(thread) + "Did not find required number of solutions \n")
        #     outfp.flush()
        #     # exit(1)

    os.unlink(inputFile+'.samples')
    os.unlink(inputFile+'.samples.valid')

    return solreturnList


def constructNewFile2(tempFile, var, indVarList):
    # print(var)
    f = open(tempFile, "r")
    lines = f.readlines()
    f.close()
    # print(indVarList, var)
    # indVarList.remove(abs(var))
    
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
    # for var in vars:
    #     solClause += str(var) + ' 0\n'
 
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

# def addClique(inputFile, indVarList, newFile):
    # f = open(inputFile, "r")
    # lines = f.readlines()
    # f.close()
    
    # #---------------------Old Clause---------------------#
    # oldClauseStr = ""
    # for line in lines:
    #     if line.strip().startswith("p cnf"):
    #         numVar = int(line.strip().split()[2])
    #         numClause = int(line.strip().split()[3])
    #     else:
    #         if line.strip().startswith("w"):
    #             oldClauseStr += line.strip()+"\n"
    #         elif not (line.strip().startswith("c")):
    #             oldClauseStr += line.strip()+"\n"
    # indStr = "c ind "
    # indIter = 1
    # for i in indVarList:
    #     if indIter % 10 == 0:
    #         indStr += " 0\nc ind "
    #     indStr += str(i) + " "
    #     indIter += 1
    # indStr += " 0\n"

    # numVarOrig = numVar
    # newClause = ""
    # varCount = 1
    # newVar = []

    # #-----------------------new Clique Clause (NetRel problem)--------------------#
    # for j in range(100):
    #     node_1 = numVarOrig + varCount
    #     node_2 = numVarOrig + varCount + 1
    #     edge = numVarOrig + varCount + 2
    #     varCount += 3
    #     newClause += str(-node_1) + " " + str(-edge) + " " + str(node_2) + " 0\n"
    #     newClause += str(node_1) + " " + str(-edge) + " " + str(-node_2) + " 0\n"    
    #     numClause += 2
    #     numVar += 3
    #     newVar.append(edge)
    # #------------------------------------------------------------------------------#
    # indStr += "c ind "
    # indIter = 1
    # for i in newVar:
    #     if indIter % 10 == 0:
    #         indStr += " 0\nc ind "
    #     indStr += str(i) + " "
    #     indIter += 1
    # indStr += " 0\n"

    # headStr = "p cnf " + str(numVar) + " " + str(numClause-1) + "\n"
    # writeStr = headStr + indStr
    # writeStr += oldClauseStr
    # writeStr += newClause
    
    # f = open(newFile, "w")
    # f.write(writeStr)
    # f.close()

    # return indVarList + newVar


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

    #-----------------------new Clique Clause (le problem)--------------------#
    # for j in range(55):
    #     edge12 = numVarOrig + varCount
    #     edge23 = numVarOrig + varCount + 1
    #     edge13 = numVarOrig + varCount + 2
    #     # node_1 = numVarOrig + varCount
    #     # node_2 = numVarOrig + varCount + 1
    #     # edge = numVarOrig + varCount + 2
    #     varCount += 3
    #     newClause += str(-edge12) + " " + str(-edge23) + " " + str(edge13) + " 0\n"    
    #     numClause += 1
    #     numVar += 3
    #     newVar+= [edge12, edge23, edge13]
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
                # newline = ' '.join(newVarbuf)
                # newVar += newVarbuf
                # newClause += newline+"\n"
    
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
            # print("##############################gbas gbas gbas", x[i], " and ", samp[i])
            # print(thread, samp[0], x[ith], ith)
            assert abs(samp[ith]) == abs(x[ith])
            if not (samp[ith] > 0) ^ (x[ith] > 0): 
                # print("test ##############################gbas gbas gbas", x[i], " and ", samp[i])
                s += 1
            r += _exp(1)
        seed += 1
        k_ = k - s
        if nloops > cut_thresh:
            outfp.write("exiting with current heads : " + str(s) + " out of " + str(k)+ " | exp rv: " + str(r) + "\n")
            outfp.flush()
            break
        # outfp.write(" current heads : " + str(s) + " " + str(k_)+ " " + str(r))
        # outfp.flush()

    return (k - 1) / r, totsamples
    
def estimate(x, dim, indVarList, tempFile, samplerType, seed, k, outfp, threadid):
    n = dim
    est = 1  
    # outfp.write("\n " + str(threadid) + "##### estimating dimension " +  str(0) + " of " + str(n))
    # outfp.flush()
    totsamples = 0
    start_time = time.time()
    out, nsamples = gbas(x, 0, indVarList, tempFile, samplerType, seed, k, outfp, threadid); out = min(1, out)
    est *= out
    totsamples += nsamples
    end_time = time.time()
    outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(0) + " of " + str(n) + " : " + str(est) + "  | time taken : " + str(end_time - start_time))
    outfp.flush()
    indVarList = constructNewFile2(tempFile, x[0], indVarList)
    for i in range(1, n):
        # outfp.write("\n " + str(threadid) + "###### estimating dimension " +  str(i) + " of " + str(n))
        # outfp.flush()
        start_time = time.time()
        out, nsamples= gbas(x, i, indVarList, tempFile, samplerType, seed, k, outfp, threadid); out = min(1, out)
        est *= out
        totsamples += nsamples
        end_time = time.time()
        outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(i) + " of " + str(n) + " : " + str(out) + "  | time taken : " + str(end_time - start_time))
        outfp.flush()
        indVarList = constructNewFile2(tempFile, x[i], indVarList)
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
    # os.unlink(tempFile_th)
    


def CubeProbe():

    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zeta", type=float, help="default = 0.3", default=0.3, dest="zeta"
    )
    parser.add_argument(
        "--eta", type=float, help="default = 0.65", default=0.65, dest="eta"
    )
    parser.add_argument(
        "--epsilon", type=float, help="default = 0.05", default=0.05, dest="epsilon"
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
    parser.add_argument("--input", help="input file", dest="input", default="avgdeg_3_008_0.cnf")
    parser.add_argument("--output", help="output file", dest="output", default="outavgtmp")
    
    args = parser.parse_args()

    samplerType = args.samplertype
    
    UserInputFile = args.input
    UserIndVarList = parseIndSupport(UserInputFile)

    # Current Working File
    inputFilePrefix = "sampler_" + str(samplerType) + "_" + UserInputFile.split("/")[-1][:-4]
    inputFile = inputFilePrefix + ".cnf"
    # indVarList = addClique(UserInputFile, UserIndVarList, inputFile)
    indVarList = UserIndVarList
    cmd = 'cp ' + UserInputFile + ' ' + inputFile
    os.system(cmd)

    # get the model count
    mcFile = inputFilePrefix + ".mc"
    cmd = "approxmc " + UserInputFile + " > "  + mcFile
    os.system(cmd)
    print(cmd)

    with open(mcFile) as fp:
        lines = fp.readlines()

    mc = 0
    for line in lines:
        if line.strip().startswith('s mc') :
            mc = line.strip().split(' ')[-1]
    mc = int(mc)
    # print(mc)
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
    # numSolutions = math.ceil(24 * (2 * eta + epsilon) / (eta - epsilon )**2 * math.log(2 / delta))
    numSolutions = math.ceil(2 / (zeta ** 2) * math.log(4 / delta)) 
    delta_m = delta / (2 * numSolutions)
    K = (epsilon + eta) / 2
    # gamma = min(1/3 , (eta - epsilon) / 2)
    gamma = zeta / (1 + zeta)
    epsilon_ = gamma / 1.107
    k = math.ceil(2 * n / epsilon_**2 * (1 /( 1 - 4 / 3 * epsilon_ / math.sqrt(n))) * math.log(2 * n / delta_m))
    print(k, numSolutions, n, epsilon_)
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
            # print(len(sampleSet[eachthread[i-1]: eachthread[i]]))
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

    if val / numSolutions > K:
        out.write("\n REJECTED")
    else:
        out.write("\n ACCEPTED")

    out.close()

    # os.unlink(inputFile)

if __name__ == "__main__":
    CubeProbe()
