import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "input", help="input file"
)
args = parser.parse_args()

filename = args.input
fp = open(filename, "r")
lines = fp.readlines()
fp.close()

#---------------------------Old formula--------------------------#
oldClauseStr = ""
dependentVars = []
for line in lines:
    if line.strip().startswith("p cnf"):
        numVar = int(line.strip().split()[2])
        numClause = int(line.strip().split()[3])
    else:
        if line.strip().startswith("w"):
            oldClauseStr += line.strip()+"\n"
        elif not (line.strip().startswith("c")):
            oldClauseStr += line.strip()+"\n"
    if len(line.strip().split()) == 2:
        dependentVars.append(abs(int(line.strip().split()[0])))	# already set values are not considered as a dependent variables

indVarList = list(range(1 , numVar+1))

#print(dependentVars)
for var in dependentVars:
    indVarList.remove(var)

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
writeStr += oldClauseStr

f = open(filename, "w")
f.write(writeStr)
f.close()



