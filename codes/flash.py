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

cwd = os.getcwd()+"/codes/WAPS"
sys.path.append(cwd)

# from waps import sampler as samp
# import weightcount.WeightCount as chainform


SAMPLER_UNIGEN3 = 7
SAMPLER_QUICKSAMPLER = 1
SAMPLER_STS = 2
SAMPLER_CMS = 4
SAMPLER_APPMC3 = 5
SAMPLER_CUSTOM = 6
SAMPLER_SPUR = 3
SAMPLER_WAPS = 8


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


def tilt(weight_map, sample1, sample2, UserIndVarList):
    tilt = 1.0
    sample1_w = copy.deepcopy(sample1)
    sample2_w = copy.deepcopy(sample2)

    sample1_w.sort(key=abs)
    sample2_w.sort(key=abs)

    for i in range(len(sample1_w)):
        litWeight = weight_map.get(abs(sample1_w[i]),0.5)
        if (sample1_w[i] > sample2_w[i]):
            tilt *= litWeight/(1-litWeight)
        elif(sample1_w[i] < sample2_w[i]):
            tilt *= (1-litWeight)/litWeight

    return tilt


def weightFactor(weight_map, sample1, sample2, UserIndVarList, eps):
    sample1_w = copy.deepcopy(sample1)
    sample2_w = copy.deepcopy(sample2)

    sample1_w.sort(key=abs)
    sample2_w.sort(key=abs)

    tilt1 = 1.0
    tilt2 = 1.0
    for i in range(len(sample1_w)):
        litWeight = weight_map.get(abs(sample1_w[i]),0.5)
        if sample1_w[i] > 0 and sample2_w[i] < 0:
            tilt1 *= litWeight/(1-litWeight)
        elif sample1_w[i] < 0 and sample2_w[i] > 0:
            tilt2 *= litWeight/(1-litWeight)

    print("tilt1 (sigma1 / zer0): {0}, tilt2 (sigma2 / zer0): {1}".format(tilt1, tilt2))
    factor1 = (tilt1 + tilt2) / (tilt1 + tilt2  + 1) #- ( 2 * math.e * (1 + eps) - 1))
    factor2 = (tilt1 + tilt2 - eps) / (tilt1 + tilt2  + 1)

    return factor1, factor2


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


def getSolutionFromUniGen3(inputFile, numSolutions, indVarList):
    #inputFilePrefix = inputFile.split("/")[-1][:-4]
    tempOutputFile = inputFile + ".txt"
    f = open(tempOutputFile, "w")
    f.close()

    cmd = './samplers/unigen3  -v 0 --samples ' + str(numSolutions) + ' --multisample 1 --kappa 0.635'
    cmd += ' --sampleout ' + str(tempOutputFile)
    cmd += ' ' + inputFile + ' > /dev/null 2>&1'

    print(cmd)
    os.system(cmd)
    f = open(tempOutputFile, "r")
    lines = f.readlines()
    f.close()
    solList = []
    for line in lines:
        line = line.strip(" 0\n")
        sample = line.split()
        sample = [int(i) for i in sample]
        solList.append(sample)

    solreturnList = solList
    if (len(solList) > numSolutions):
        solreturnList = random.sample(solList, numSolutions)

    os.unlink(str(tempOutputFile))
    return solreturnList


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


def getSolutionFromAppmc3(inputFile, numSolutions, indVarList):
    #inputFilePrefix = inputFile.split("/")[-1][:-4]
    tempOutputFile = inputFile + ".txt"
    f = open(tempOutputFile, "w")
    f.close()
    cmd = (
        "./samplers/approxmc3 "
        + inputFile
        + " --samples "
        + str(numSolutions)
        + " --sampleout "
        + str(tempOutputFile)
        #+ " > /dev/null 2>&1"
    )
    print(cmd)
    os.system(cmd)
    f = open(tempOutputFile, "r")
    lines = f.readlines()
    f.close()
    solList = []
    for line in lines:
        line = line.strip()
        freq = int(line.split(":")[0].strip())
        for _ in range(freq):
            sample = line.split(":")[1].strip()[:-2]
            sample = sample.split()
            sample = [int(i) for i in sample]
            solList.append(sample)

    solreturnList = solList
    if (len(solList) > numSolutions):
        solreturnList = random.sample(solList, numSolutions)

    os.unlink(str(tempOutputFile))
    return solreturnList



# @CHANGE_HERE : please make changes in the below block of code
""" this is the method where you could run your sampler for testing
Arguments : input file, number of solutions to be returned, list of independent variables
output : list of solutions """


def getSolutionFromCustomSampler(inputFile, numSolutions, indVarList):
    solreturnList = []
    """ write your code here """

    return solreturnList


def getSolutionFromSampler(inputFile, numSolutions, samplerType, indVarList, seed, thread, outfp):

    if samplerType == SAMPLER_UNIGEN3:
        return getSolutionFromUniGen3(inputFile, numSolutions, indVarList)
    if samplerType == SAMPLER_QUICKSAMPLER:
        return getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed, thread, outfp)
    if samplerType == SAMPLER_STS:
        return getSolutionFromSTS(seed, inputFile, numSolutions, indVarList)
    if samplerType == SAMPLER_SPUR:
        return getSolutionFromSpur(seed, inputFile, numSolutions, indVarList)
    if samplerType == SAMPLER_CMS:
        return getSolutionFromCMSsampler(inputFile, numSolutions, indVarList, seed)
    if samplerType == SAMPLER_APPMC3:
        return getSolutionFromAppmc3(inputFile, numSolutions, indVarList)
    if samplerType == SAMPLER_CUSTOM:
        return getSolutionFromCustomSampler(inputFile, numSolutions, indVarList)
    else:
        print("Error")
        return None


def getSolutionFromSTS(seed, inputFile, numSolutions, indVarList):
    kValue = 50

    while True:
        samplingRounds = int(numSolutions/kValue) + 1
        inputFileSuffix = inputFile.split('/')[-1][:-4]
        outputFile = tempfile.gettempdir()+'/'+inputFileSuffix+"sts.out"
        cmd = './samplers/STSnew -k='+str(kValue)+' -nsamples='+str(samplingRounds)+' -rnd-seed=' + str(seed) +' '+str(inputFile)
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
        if len(solList) > numSolutions:
            solreturnList = random.sample(solList, numSolutions)
            break
        elif len(solList) < numSolutions:
            print(len(solList), numSolutions)
            # print(solList)
            print("STS Did not find required number of solutions")
            # sys.exit(1)
            kValue = int(kValue / 5) + 1


    os.unlink(outputFile)
    return solreturnList



def getSolutionFromQuickSampler(inputFile, numSolutions, indVarList, seed, thread, outfp):
    multiplier = 5
    if numSolutions < 100 : multiplier = 10
    # cmd ='approxmc -v 0 ' + inputFile + ' > checkherethenumber'
    # os.system(cmd)
    solreturnList = []
    while True:
        cmd = (
            "./samplers/quicksampler"+ str(thread) +" -n "
            + str(numSolutions * multiplier)
            + " "
            + str(inputFile)
            #+ " > /dev/null 2>&1"
            )
        os.system(cmd)
        cmd = "./samplers/z3"+ str(thread) +" " + str(inputFile) #+ " > /dev/null 2>&1"
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
        print("lines:", len(lines), inputFile)
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
            solreturnList = random.sample(solreturnList, numSolutions) # this should not be numsolutinos to fix
            break
        elif len(solreturnList) < numSolutions:
            outfp.write(str(thread) + str(len(solList)) + str(numSolutions))
            outfp.flush()
            # print(solList[0])
            outfp.write(str(thread) + "Did not find required number of solutions \n")
            outfp.flush()
            # exit(1)

    os.unlink(inputFile+'.samples')
    os.unlink(inputFile+'.samples.valid')

    return solreturnList


def getSolutionFromWAPS(inputFile, numSolutions):
    sampler = samp(cnfFile=inputFile)
    sampler.compile()
    sampler.parse()
    sampler.annotate()
    samples = sampler.sample(totalSamples=numSolutions)
    solList = list(samples)
    solList = [i.strip().split() for i in solList]
    solList = [[int(x) for x in i] for i in solList]
    return solList

def project(sample, VarList):
    '''
    project sample on the VarList
    '''
    projectedSample = []
    for s in sample:
        if abs(s) in VarList:
            projectedSample.append(s)
    return projectedSample


def check_cnf(fname):
    """
    validating structure of .cnf
    """

    with open(fname, 'r') as f:
        lines = f.readlines()

    given_vars = None
    given_cls = None
    cls = 0
    max_var = 0
    for line in lines:
        line = line.strip()

        if len(line) == 0:
            print("ERROR: CNF is incorrectly formatted, empty line!")
            return False

        line = line.split()
        line = [l.strip() for l in line]

        if line[0] == "p":
            assert len(line) == 4
            assert line[1] == "cnf"
            given_vars = int(line[2])
            given_cls = int(line[3])
            continue

        if line[0] == "c" or line[0] == "w":
            continue

        cls +=1
        n_pos_lit = 0
        for l in line:
            var = abs(int(l))
            max_var = max(var, max_var)
            if (var == int(l) and var != 0):
                n_pos_lit += 1

        if n_pos_lit > 1:
            # number of positive literal is atmost 1 in Horn caluses
            print("ERROR: Not a valid Horn formula")
            return False

    if max_var > given_vars:
        print("ERROR: Number of variables given is LESS than the number of variables ued")
        print("ERROR: Vars in header: %d   max var: %d" % (given_vars, max_var))
        return False

    if cls != given_cls:
        print("ERROR: Number of clauses in header is DIFFERENT than the number of clauses in the CNF")
        print("ERROR: Claues in header: %d   clauses: %d" % (given_cls, cls))
        return False

    return True


def findWeightsForVariables(sampleSol, idealSol, numSolutions):
    """
    Finds rExtList
    """
    countList = []
    newVarList = []
    lenSol = len(sampleSol)
    # print("sampleSol:", sampleSol)
    tau = min(3,len(sampleSol))

    for _ in range(tau):
        countList.append(5)
        newVarList.append(4)
    rExtList = []
    oldVarList = []

    indexes = random.sample(range(len(sampleSol)), len(countList))

    idealVarList = [idealSol[i] for i in indexes]
    sampleVarList = [sampleSol[i] for i in indexes]

    print("idealVarList:", idealSol)
    print("sampleVarList:", sampleSol)
    print("idealVarList:", idealVarList)
    print("sampleVarList:", sampleVarList)

    assert len(idealVarList) == len(sampleVarList)
    for a, b in zip(idealVarList, sampleVarList):
        assert abs(int(a)) == abs(int(b))

    oldVarList.append(sampleVarList)
    oldVarList.append(idealVarList)
    rExtList.append(countList)
    rExtList.append(newVarList)
    rExtList.append(oldVarList)

    return rExtList


def pushVar(variable, cnfClauses):
    cnfLen = len(cnfClauses)
    for i in range(cnfLen):
        cnfClauses[i].append(variable)
    return cnfClauses


def getCNF(variable, binStr, sign, origTotalVars):
    cnfClauses = []
    binLen = len(binStr)
    if sign:
        cnfClauses.append([-(binLen + 1 + origTotalVars)])
    else:
        cnfClauses.append([binLen + 1 + origTotalVars])
    for i in range(binLen):
        newVar = int(binLen - i + origTotalVars)
        if sign == False:
            newVar = -1 * (binLen - i + origTotalVars)
        if binStr[binLen - i - 1] == "0":
            cnfClauses.append([int(-1 * newVar)])
        else:
            cnfClauses = pushVar(int(-1 * newVar), cnfClauses)
    pushVar(variable, cnfClauses)
    return cnfClauses


def constructChainFormula(originalVar, solCount, newVars, origTotalVars, invert):
    writeLines = ""
    binStr = str(bin(int(solCount)))[2:-1]
    binLen = len(binStr)
    for i in range(newVars - binLen - 1):
        binStr = "0" + binStr

    firstCNFClauses = getCNF(-int(originalVar), binStr, invert, origTotalVars)
    addedClauseNum = 0
    for i in range(len(firstCNFClauses)):
        addedClauseNum += 1
        for j in range(len(firstCNFClauses[i])):
            writeLines += str(firstCNFClauses[i][j]) + " "
        writeLines += "0\n"
    CNFClauses = []
    for i in range(len(CNFClauses)):
        if CNFClauses[i] in firstCNFClauses:
            continue
        addedClauseNum += 1
        for j in range(len(CNFClauses[i])):
            writeLines += str(CNFClauses[i][j]) + " "
        writeLines += "0\n"
    return (writeLines, addedClauseNum)


def newVars(numSolutions, Vars):
    """
    Returns relevant information for Chain formula blowup
    """

    n = len(Vars)
    N = numSolutions

    tau = min(4, n)

    N_ = int(math.ceil(N**(1/tau)))

    # for each commonVar we need to add one chain formula with x variables
    x = int(math.ceil(math.log(N_,2)))
    extendedList = []
    countList = []
    numVarList = []

    for _ in range(tau):
        countList.append(int(2**(x+1) - 1))
        numVarList.append(x+1)

    varsForchain = random.sample(Vars, len(countList))

    extendedList.append(countList)      # K list
    extendedList.append(numVarList)     # m list
    extendedList.append(varsForchain)
    return extendedList


def getSamples(inputFile, tempFile, indVarList, samplerType, seed, bsize):
    n = math.ceil(len(indVarList) / bsize)
    print(100*"=" + "getsamples with indVarList size " + str(n))
    samp = []
    rho = getSolutionFromSampler(inputFile, 1, samplerType, indVarList, seed)[0]
    samp += rho[:bsize]
    indVarList = constructNewFile(inputFile, tempFile, rho[:bsize], indVarList)
    # print(indVarList)
    for i in range(1, n):
        rho = getSolutionFromSampler(tempFile, 1, samplerType, indVarList, seed)[0]
        samp += rho[:bsize]
        indVarList = constructNewFile(tempFile, tempFile, rho[:bsize], indVarList)
        # print(indVarList)
    print(samp)
    return samp


# @returns whether new file was created and the list of independent variables
def constructNewFile(inputFile, tempFile, vars, indVarList):
    # print(var)
    f = open(inputFile, "r")
    lines = f.readlines()
    f.close()
    for var in vars:
        indVarList.remove(abs(var))

    #---------------------------Old formula--------------------------#5
    oldClauseStr = ""
    for line in lines:
        if line.strip().startswith("p cnf"):
            numVar = int(line.strip().split()[2])
            numClause = int(line.strip().split()[3]) + len(vars)
        else:
            if line.strip().startswith("w"):
                oldClauseStr += line.strip()+"\n"
            elif not (line.strip().startswith("c")):
                oldClauseStr += line.strip()+"\n"


    #----------------Adding constraints-------------------#
    solClause = ""
    for var in vars:
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

def constructNewFile2(tempFile, var, indVarList):
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


def gbas(x, i, indVarList, tempfile, samplerType, seed, k, outfp, thread):
    s, r = 0, 0
    k_ = int(k)
    k = k_
    cut_thresh = 40
    nloops = 0
    while s < k:
        nloops += 1
        sampSet = getSolutionFromSampler(tempfile, k_, samplerType, indVarList, seed, thread, outfp)
        for samp in sampSet:
            # print("##############################gbas gbas gbas", x[i], " and ", samp[i])
            if not (samp[i] > 0) ^ (x[i] > 0): 
                # print("test ##############################gbas gbas gbas", x[i], " and ", samp[i])
                s += 1
            r += _exp(1)
        seed += 1
        k_ = k - s
        if nloops > cut_thresh:
            outfp.write("exiting with current heads : " + str(s) + " out of " + str(k)+ " | exp rv: " + str(r) + "\n")
            outfp.flush()
            break
        outfp.write(" current heads : " + str(s) + " " + str(k_)+ " " + str(r))
        outfp.flush()

    return (k - 1) / r
    
def estimate(x, dim, indVarList, tempFile, samplerType, seed, k, outfp, threadid):
    n = dim
    est = 1  
    outfp.write("\n " + str(threadid) + "##### estimating dimension " +  str(0) + " of " + str(n))
    outfp.flush()
    start_time = time.time()
    est *= min(1, gbas(x, 0, indVarList, tempFile, samplerType, seed, k, outfp, threadid))
    end_time = time.time()
    outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(0) + " of " + str(n) + " : " + str(est) + "  | time taken : " + str(end_time - start_time))
    outfp.flush()
    indVarList = constructNewFile2(tempFile, x[0], indVarList)
    for i in range(1, n):
        outfp.write("\n " + str(threadid) + "###### estimating dimension " +  str(i) + " of " + str(n))
        outfp.flush()
        start_time = time.time()
        est *= min(1, gbas(x, i, indVarList, tempFile, samplerType, seed, k, outfp, threadid))
        end_time = time.time()
        outfp.write("\n Thread " + str(threadid) + " estimated dimension " +  str(i) + " of " + str(n) + " : " + str(est) + "  | time taken : " + str(end_time - start_time))
        outfp.flush()
        indVarList = constructNewFile2(tempFile, x[i], indVarList)
    return est

def bias(x, j, indVarList, tempFile, samplerType, nsamp, seed, bsize):
    print("nsampbias" , nsamp, j)
    val = 0
    ksamp = 20000
    for _ in range(math.floor(nsamp / ksamp)):
        sampSet = getSolutionFromSampler(tempFile, ksamp, samplerType, indVarList, seed)
        for samp in sampSet:
            if x[j * bsize: (j+1) * bsize] == samp[j* bsize: (j+1) * bsize]: val += 1
    return val / nsamp

# def constructKernel(inputFile, tempFile, samplerSample, idealSample, numSolutions, origIndVarList):
#     # rExtList = findWeightsForVariables(samplerSample, idealSample, numSolutions)
#     # print("rExtList:", rExtList)
#     tempIndVarList = constructNewFile(inputFile, tempFile, samplerSample, idealSample, origIndVarList, numSolutions)
#     return tempIndVarList


def inthread(sampleSet, dim, indVarList, inputFile, samplerType, seed, k, out, est, threadid):
    tempFile_th= "thread_" + str(threadid) + "_" + inputFile
    cmd = "cp " + inputFile + " ./" + tempFile_th 
    for x in sampleSet:
        os.system(cmd)
        est.append(estimate(x, dim, indVarList, tempFile_th, samplerType, seed, k, out, threadid))


def flash():

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
        help=str(SAMPLER_UNIGEN3)
        + " for UniGen3;\n"
        + str(SAMPLER_QUICKSAMPLER)
        + " for QuickSampler;\n"
        + str(SAMPLER_STS)
        + " for STS;\n",
        default=SAMPLER_QUICKSAMPLER,
        dest="samplertype",
    )
    parser.add_argument("--seed", type=int, dest="seed", default=420)
    parser.add_argument("input", help="input file")
    parser.add_argument("output", help="output file")
    parser.add_argument("--thread", help="default use thread", default=1)

    args = parser.parse_args()

    samplerType = args.samplertype
    
    UserInputFile = args.input
    UserIndVarList = parseIndSupport(UserInputFile)

    # Current Working File
    inputFilePrefix = "sampler_" + str(samplerType) + "_" + UserInputFile.split("/")[-1][:-4]
    inputFile = inputFilePrefix + ".cnf"
    indVarList = addClique(UserInputFile, UserIndVarList, inputFile)

    # get the model count
    mcFile = "sampler_" + str(samplerType) + "_mc.out"
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

    # set up the parameters
    isthread = args.thread
    eta = args.eta
    epsilon = args.epsilon
    delta = args.delta
    outputFile = args.output
    seed = args.seed
    random.seed(seed)

    tempFile = inputFile.split(".")[0] + "_t.cnf"

    samplerString = ""

    if samplerType == SAMPLER_UNIGEN3:
        samplerString = "UniGen3"
    if samplerType == SAMPLER_QUICKSAMPLER:
        samplerString = "QuickSampler"
    if samplerType == SAMPLER_STS:
        samplerString = "STS"
    if samplerType == SAMPLER_CUSTOM:
        samplerString = "CustomSampler"
    if samplerType == SAMPLER_APPMC3:
        samplerString = "AppMC3"
    if samplerType == SAMPLER_CMS:
        samplerString = "CMSGen"

    
    #----------------------------------------- parameter calculation----------------------------------------------
    n = len(UserIndVarList) 
    numSolutions = math.ceil((4 * eta - 3 * epsilon) / (eta - 5 * epsilon / 2)**2 * math.log(2 / delta))
    delta_m = delta / (2 * numSolutions)
    K = (epsilon + eta)
    epsilon_ = epsilon / 1.107
    k = math.ceil(2 * n / epsilon_**2 * (1 /( 1 - 4 / 3 * epsilon_ / math.sqrt(n))) * math.log(2 * n / delta_m))
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

    val = 0
    out = open(outputFile, "a")
    
    if isthread == 1:
        
        t = []
        total_cores = 22            # tofix
        ncores = total_cores    # tofix

        eachthread = [numSolutions // ncores for i in range(ncores)]
        rem = numSolutions % ncores
        for i in range(ncores):
            eachthread[i] += 1
            rem -= 1
            if rem == 0 : break
        for i in range(1, ncores):
            eachthread[i] += eachthread[i-1]

        massarray = []

        for i in range(ncores):
            # tempFile_th= "thread_" + str(i) + "_" + inputFile
            # cmd = "cp " + inputFile + " ./" + tempFile_th 
            # os.system(cmd)
            t.append(threading.Thread(target=inthread, args=(sampleSet[eachthread[max(0, i-1)]: eachthread[i]], dim, indVarList, inputFile, samplerType, seed, k, out, massarray, i)))
        
        for i in range(ncores):
            t[i].start()
        for i in range(ncores):
            t[i].join()

        out.write("estimated weights : " + str(massarray) + "\n")
        out.flush()

        for est in massarray:
            val += abs(1 - 1 /(est * mc))
    
        
    else:

        val = 0
        count = 0
    
        for x in sampleSet:
            out.write(str(count) + " of " + str(len(sampleSet)) + "\t")
            out.flush()
            est = estimate(x, dim, indVarList, inputFile, samplerType, seed, k, out, 1)
            val = val + abs(1 - 1 / (est * mc) )
            count += 1

    out.write("\n dTV estimated : " + str(val / numSolutions))

    if val / numSolutions > K:
        out.write("REJECTED")
    else:
        out.write("ACCEPTED")

    out.close()

if __name__ == "__main__":
    flash()
