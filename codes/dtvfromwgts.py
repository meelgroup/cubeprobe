import os
import argparse, re

parser = argparse.ArgumentParser()
parser.add_argument(
        "input", help="input",
    )
parser.add_argument(
        "output", help="output",
    )
args = parser.parse_args()

fp = open(args.input, "r")
lines = fp.readlines()
fp.close()

dims = lines[1].strip().split()[0]

for line in lines:
    if line.startswith(" estimated"):
        estwgts = eval(line.strip().split(":")[1])
        
numsamp = 0
for line in lines:
    if re.search("nsolns", line):
        try:
            numsamp += int(line.strip().split(":")[-1])
        except ValueError:
            numsamp += int(line.strip().split(":")[-1].split(".")[0]) + 1
            
# get the model count [approxmc]
inputFilePrefix = args.input.strip().split("/")[-1][10:-4]
mcFile = inputFilePrefix + ".mc"
cmd = "approxmc bench_Lext/" + inputFilePrefix + ".cnf > "  + mcFile
os.system(cmd)

with open(mcFile) as fp:
    lines = fp.readlines()

mc = 0
for line in lines:
    if line.strip().startswith('s mc') :
        mc = line.strip().split(' ')[-1]
mc = int(mc)
print(mc)
os.unlink(mcFile)

# # get the model count [approxmc]
# inputFilePrefix = args.input.strip().split("/")[-1][10:-4]
# print(inputFilePrefix)
# mcFile = inputFilePrefix + ".mc"
# cmd = "./samplers/sharpSAT -decot 1 -decow 100 -tmpdir . -cs 3500 bench/" + inputFilePrefix + ".cnf > "  + mcFile
# os.system(cmd)
# print(cmd)

# with open(mcFile) as fp:
#     lines = fp.readlines()

# mc = 0
# for line in lines:
#     if line.strip().startswith('c s exact') :
#         mc = line.strip().split(' ')[-1]
# mc = int(mc)
# print(mc)
# os.unlink(mcFile)

dTV = 0
for wgt in estwgts:
    dTV += max(0, 1 - 1 / (mc * wgt))

dTV /= len(estwgts)

if dTV < 0.31:
    result = "ACCEPT"
else:
    result = "REJECT"

fp = open(args.output, "a")
fp.write(inputFilePrefix + " " + dims + " " + str(dTV) + " " + str(numsamp) + " " + result + "\n")
fp.close()
