import sys
import os
import tempfile

tempDir = tempfile.gettempdir()
processrankStr = os.environ.get("OMPI_COMM_WORLD_RANK")
allocatedCores = os.environ.get("OMPI_UNIVERSE_SIZE")

if (processrankStr == None):
    processrankStr = 0
processrank = int(processrankStr)

nsamples = 44; ndim = 91
eachcpu = allocatedCores // nsamples
dirnum = processrank // eachcpu
dim = processrank % eachcpu

samplerType = 1

#cmd = 'ulimit -v 4000000; python Verifier.py --sampler '+str(samplerType)+' --inverted 1 --reverse 0 --seed 0 --exp 1000 '+filepos+'  outDir/sampler_'+str(samplerType)+'_'+fileSuffix+'.out'
#print(cmd)
# cmd = 'python3 flash.py --sampler '+str(samplerType)+' --seed 420 '+filepos+'  outDir/sampler_'+str(samplerType)+'_'+fileSuffix+'.out'
# os.system(cmd)

cmd = 'ulimit -v 4000000; python3 estimate.py --sampleID ' + str(dirnum) + ' --dimension ' + str(dim) + \
    ' bench_RelNet/Net6_count_91.cnf ' + '--sampler ' + str(samplerType)
os.system(cmd)