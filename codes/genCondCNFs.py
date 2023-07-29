# This script is maintained to generate samples and to create conditioned CNFS to parallel process on nscc cluster

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
SAMPLER_SPUR = 3
SAMPLER_CMS = 4



def parseIndSupport(indSupportFile):  
    # returns List of Independent Variables
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

    cmd = "./samplers/cryptominisat5 --restart fixed --maple 0 --verb 0 --nobansol"
    cmd += " --scc 1 -n 1 --presimp 0 --polar rnd --freq 0.9999 --fixedconfl 100"
    cmd += " --random " + str(newSeed) + " --maxsol " + str(numSolutions)
    cmd += " --dumpresult " + tempOutputFile
    cmd += " " + inputFile + " > /dev/null 2>&1"

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


def getSolutionFromSampler(inputFile, numSolutions, samplerType, indVarList, seed):

    if samplerType == SAMPLER_QUICKSAMPLER:
        return getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed)
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

    while True:
        samplingRounds = int(numSolutions/kValue) + 1
        inputFileSuffix = inputFile.split('/')[-1][:-4]
        outputFile = tempfile.gettempdir()+'/'+inputFileSuffix+"sts.out"
        cmd = './samplers/STS -k='+str(kValue)+' -nsamples='+str(samplingRounds)+' -rnd-seed=' + str(seed) +' '+str(inputFile)
        cmd += ' > '+str(outputFile)
        #if args.verbose:
        #    print("cmd: ", cmd)
        # print(cmd)
        os.system(cmd)

        with open(outputFile, 'r') as f:
            lines = f.readlines()
            
        solList = []
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
                for x in list(lines[j].strip()):
                    if (x == '0'):
                        sol.append(-1*indVarList[i])
                    else:
                        sol.append(indVarList[i])
                    i += 1
                solList.append(sol)

        solreturnList = solList
        if len(solList) > numSolutions:
            solreturnList = random.sample(solList, numSolutions)
            break
        elif len(solList) < numSolutions:
            print(len(solList))
            # print(solList)
            print("STS Did not find required number of solutions")
            # sys.exit(1)
            kValue = int(kValue / 5) + 1


    os.unlink(outputFile)
    return solreturnList


def getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed):
    cmd = (
        "./samplers/quicksampler -n "
        + str(numSolutions * 5)
        + " "
        + str(inputFile)
        #+ " > /dev/null 2>&1"
        )
    print(cmd)
    os.system(cmd)
    cmd = "./samplers/z3 " + str(inputFile) #+ " > /dev/null 2>&1"
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

    solreturnList = solList
    if len(solList) > numSolutions:
        solreturnList = random.sample(solList, numSolutions)
    elif len(solreturnList) < numSolutions:
        print("Did not find required number of solutions")
        exit(1)

    os.unlink(inputFile+'.samples')
    os.unlink(inputFile+'.samples.valid')

    return solreturnList



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

    #-----------------------new Clique Clause (RelNet problem)-------------------#
    newnumVar, newnumClause = 0, 0
    for j in range(18):
        node_1 = numVarOrig + varCount
        node_2 = numVarOrig + varCount + 1
        edge = numVarOrig + varCount + 2
        varCount += 3
        newClause += str(-node_1) + " " + str(-edge) + " " + str(node_2) + " 0\n"
        newClause += str(node_1) + " " + str(-edge) + " " + str(-node_2) + " 0\n"    
        # numClause += 2
        # numVar += 3
        newnumClause += 2
        newnumVar += 3
        newVar.append(edge)

    # #-----------------------new Clique Clause (le problem)--------------------#
    # fmt = open("empty.cnf", "r")
    # mtlines = fmt.readlines()
    # fmt.close()
    
    # for line in mtlines:
    #     if line.strip().startswith("p cnf"):
    #         newnumVar = int(line.strip().split()[2])
    #         newnumClause = int(line.strip().split()[3])
    #     else:
    #         if line.strip().startswith("w"):
    #             newClause += line.strip()+"\n"
    #         elif not (line.strip().startswith("c")):
    #             newVarbuf = [int(_var) for _var in line.strip().split()]
    #             for _var in newVarbuf:
    #                 if _var > 0:
    #                     newClause += str(abs(_var) + numVar) + ' '
    #                 elif _var < 0:
    #                     newClause += str( -1 * (abs(_var) + numVar)) + ' '
    #                 newVar.append(abs(_var) + numVar)
    #             newClause += '0\n' 
    #             # newline = ' '.join(newVarbuf)
    #             # newVar += newVarbuf
    #             # newClause += newline+"\n"
    # newVar = set(newVar)
    # newVar.remove(numVar)
    # newVar = sorted(list(newVar))
    
    #------------------------------------------------------------------------------#
    
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



def constructNewFile(tempFile, condvars, indVarList):
    # print(var)
    f = open(tempFile, "r")
    lines = f.readlines()
    f.close()
    # indVarList.remove(abs(var))

    #---------------------------Old formula--------------------------#
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


    #----------------Adding constraints-------------------#
    solClause = ""
    for var in condvars:
        solClause += str(var) + ' 0\n'
        numClause += 1
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

    #---------------------estimate which dimension--------------------------#
    dimStr = "c estimate " + str(condvars[-1]) +"\n"

    headStr = "p cnf " + str(numVar) + " " + str(numClause) + "\n"
    writeStr = headStr + indStr 
    writeStr += dimStr
    writeStr += solClause
    writeStr += oldClauseStr

    f = open(tempFile, "w")
    f.write(writeStr)
    f.close()
    return #indVarList


def generate():

    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eta", type=float, help="default = 0.9", default=0.9, dest="eta"
    )
    parser.add_argument(
        "--epsilon", type=float, help="default = 0.2", default=0.2, dest="epsilon"
    )
    parser.add_argument(
        "--delta", type=float, help="default = 0.2", default=0.2, dest="delta"
    )
    parser.add_argument(
        "--sampler",
        type=int,
        help= str(SAMPLER_QUICKSAMPLER)
        + " for QuickSampler;\n"
        + str(SAMPLER_STS)
        + " for STS;\n" + str(SAMPLER_SPUR) + " for SPUR;\n",
        default=SAMPLER_QUICKSAMPLER,
        dest="samplertype",
    )
    parser.add_argument("--seed", type=int, dest="seed", default=420)
    parser.add_argument("input", help="input file")

    args = parser.parse_args()

    samplerType = args.samplertype
    
    UserInputFile = args.input
    UserIndVarList = parseIndSupport(UserInputFile)
    ndim = len(UserIndVarList)

    # Current Working File
    inputFilePrefix = "sampler_" + str(samplerType) + "_" + UserInputFile.split("/")[-1][:-4]
    inputFile = inputFilePrefix + ".cnf"
    indVarList = addClique(UserInputFile, UserIndVarList, inputFile)

    # Directory for working benchmarks
    benchDir = inputFilePrefix
    cmd = "mkdir " + benchDir
    os.system(cmd)

    # get the model count
    mcFile = benchDir + "/mcount" + ".mc"
    cmd = "approxmc " + UserInputFile + " > "  + mcFile
    os.system(cmd)
    with open(mcFile) as fp:
        lines = fp.readlines()
    mc = 0
    for line in lines:
        if line.strip().startswith('s mc') :
            mc = line.strip().split(' ')[-1]
    mc = int(mc)

    # set up the parameters
    eta = args.eta
    epsilon = args.epsilon
    delta = args.delta
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
    if samplerType == SAMPLER_SPUR:
        samplerString = "SPUR"

    
    #----------------------------------------- parameter calculation----------------------------------------------
    n = len(UserIndVarList) 
    numSolutions = math.ceil((4 * eta - 3 * epsilon) / (eta - 5 * epsilon / 2)**2 * math.log(2 / delta))
    delta_m = delta / (2 * numSolutions)
    K = (epsilon + eta)
    epsilon_ = epsilon / 1.107
    k = math.ceil(2 * n / epsilon_**2 * (1 /( 1 - 4 / 3 * epsilon_ / math.sqrt(n))) * math.log(2 * n / delta_m))
    fp = open(benchDir + "/metadata.txt", "w")
    fp.write("k : " + str(k) + "\n" + "K : " + str(K) + "\n")
    fp.write("dimensions : " + str(UserIndVarList))
    fp.close()
    #--------------------------------------------------------------------------------------------------------------
    
    # f = open(outputFile, "w")
    # f.write("numSolutions: "+ str(numSolutions)+ " k : " + str(k)  + "\n" + str(n) + " " + str(numSolutions) + " " + str(epsilon / math.sqrt(n)) + " " + str(delta_m / n) + "\n")
    # f.flush()
    # f.close()
    
    #---------------------------------------------main begins---------------------------------------
    
    # cmd = "approxmc " + UserInputFile
    # os.system(cmd)
    sampleSet = []
    sampleSet = getSolutionFromSampler(inputFile, numSolutions, samplerType, indVarList, seed)

    id =1
    for sample in sampleSet:
        sampleDir = inputFilePrefix + "/" + str(id)
        cmd = "mkdir " +  sampleDir
        os.system(cmd)
        
        for dim in range(ndim):
            dimFile = sampleDir + "/" + inputFilePrefix + "_" + str(dim) + ".cnf"
            cmd = "cp " + inputFile + " " + dimFile
            os.system(cmd) 
            constructNewFile(dimFile, sample[:dim+1], indVarList)
        id += 1

    os.unlink(inputFile)

if __name__ == "__main__":
    generate()