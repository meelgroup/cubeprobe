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
        if line.startswith("c estimate"):
            toEst = int(line.strip().replace("c estimate", "").split()[0])
    if len(indList) == 0:
        indList = [int(x) for x in range(1, numVars + 1)]
    else:
        indList = [int(x) for x in indList]
    return indList, toEst


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


def getParameters(parameterFile):
    fp = open(parameterFile, "r")
    lines = fp.readlines()
    for line in lines:
        if line.startswith("k :"):
            k = int(line.strip().split(":")[1])
        if line.startswith("dimensions : "):
            dims = eval(line.strip().split(":")[1])
    return k, dims


def gbas(x_i, i, indVarList, tempfile, samplerType, seed, k):
    s, r = 0, 0
    k_ = int(k)
    k = k_
    cut_thresh = 40
    nloops = 0
    while s < k:
        nloops += 1
        sampSet = getSolutionFromSampler(tempfile, k_, samplerType, indVarList, seed)
        for samp in sampSet:
            # print("##############################gbas gbas gbas", x[i], " and ", samp[i])
            if not (samp[i] > 0) ^ (x_i > 0): 
                # print("test ##############################gbas gbas gbas", x[i], " and ", samp[i])
                s += 1
            r += _exp(1)
        seed += 1
        k_ = k - s
        if nloops > cut_thresh:
            # outfp.write("exiting with current heads : " + str(s) + " out of " + str(k)+ " | exp rv: " + str(r) + "\n")
            # outfp.flush()
            break
        # outfp.write(" current heads : " + str(s) + " " + str(k_)+ " " + str(r))
        # outfp.flush()

    return (k - 1) / r


def estimate():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sampleID", type=int, help="sample ID", dest="id"
    )
    parser.add_argument(
        "--dimension", type=int, help="dimension", dest="dim"
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

    sampID = args.id
    dim = args.dim 
    seed = args.seed
    samplerType = args.samplertype
    UserInputFile = args.input
    outputFile = args.output

    DirName = "sampler_" + str(samplerType) + "_" + UserInputFile.split("/")[-1][:-4] 
    fileName = DirName + "/" + str(sampID) + "/" + DirName +  "_" + str(dim) + ".cnf"

    k, dims = getParameters(DirName + "/metadata.txt")

    indVarList, x_i = parseIndSupport(fileName)

    est = min(1, gbas(x_i, dims[dim], indVarList, fileName, samplerType, seed, k))

    # print("estimating dimenstion ", str(dims[dim]), est)

    fp = open(DirName + "/estimates.out", "w")
    fp.write("dim_" + str(dims[dim]) + " " + str(est))
    fp.close()

if __name__ == "__main__":
    estimate()