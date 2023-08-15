import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from statistics import median

samplers = ['quick', 'sts', 'cms']
X, Y, Z = [], [], []


# # which dtv is higher in how many
# dtvs = {}

# for sampler in samplers:
#     # inputFile = "./aaai/dtv_"+sampler+"_aaai.out"
#     inputFile = "./dtv_"+sampler+"_exact.out"

#     fp = open(inputFile, "r")
#     lines = fp.readlines()
#     fp.close()

#     for line in lines:
#         name = line.strip().split(" ")[0]
#         dtv = float(line.strip().split(" ")[2])
#         if name in dtvs.keys():
#             dtvs[name] += [dtv]
            
#         else:
#             dtvs[name] = [dtv]

#     argmax = lambda lst : lst.index(max(lst))
#     argmin = lambda lst : lst.index(min(lst))

#     quickmax, stsmax, cmsmax = 0, 0, 0
#     quickmin, stsmin, cmsmin = 0, 0, 0
    
#     for key in dtvs.keys():
#         if argmax(dtvs[key]) == 0:
#             quickmax += 1 
#         elif argmax(dtvs[key]) == 1:
#             stsmax += 1
#         elif argmax(dtvs[key]) == 2:
#             cmsmax += 1
#         if argmin(dtvs[key]) == 0:
#             quickmin += 1 
#         elif argmin(dtvs[key]) == 1:
#             stsmin += 1
#         elif argmin(dtvs[key]) == 2:
#             cmsmin += 1
        
# print(quickmax, stsmax, cmsmax, quickmin, stsmin, cmsmin)

    
# avg dtv or avg nsamples (Y) vs the dimension (X) 
for sampler in samplers:
    # inputFile = "./aaai/dtv_"+sampler+"_aaai.out"
    inputFile = "./dtv_"+sampler+"_nompt.out"

    fp = open(inputFile, "r")
    lines = fp.readlines()
    fp.close()

    dict = {}
    n = {}
    dtvs = {}

    for line in lines:
        dim = int(line.strip().split(" ")[1])
        buff = line.strip().split(" ")[2]
        if buff == 'NOTEND':
            continue
        dtv = float(buff)
        nsamp = int(line.strip().split(" ")[3])
        if dim in dict.keys():
            dict[dim] += nsamp
            n[dim] += 1
            dtvs[dim] += [dtv]
            
        else:
            dict[dim] = nsamp
            n[dim] = 1
            dtvs[dim] = [dtv]

    for key in dict.keys():
        dict[key] //= n[key]
        dtvs[key] = median(dtvs[key])

    X += list(dtvs.keys())
    Y += list(dtvs.values())
    if sampler == 'sts':
        sampler = r'$\mathtt{LxtSTS}$'
    if sampler == 'quick':
        sampler = r'$\mathtt{LxtQuicksampler}$'
    if sampler == 'cms':
        sampler = r'$\mathtt{LxtCMSGen}$'
    Z += [sampler] * len(dtvs)

# plt.scatter(X, Y)
# plt.show()

plt.rcParams["mathtext.fontset"] = 'stix'
                              
df = pd.DataFrame(list(zip(X, Y, Z)),
               columns =['Dimension', 'Estd TV distance', 'Samplers'])
print(df)
# sns.scatterplot(df, x="dimension", y="samples", hue="sampler", legend="full")
sns.lineplot(df, x="Dimension", y="Estd TV distance", hue="Samplers", legend="full", style="Samplers", markers=True)
# plt.plot(df["dimension"], df["Estd TV distance"])
plt.show()

# # avg dtv (Y) vs becnhmark sorted in dtv order (X) 
# flag = 0
# for sampler in samplers:
#     inputFile = "./aaai/dtv_"+sampler+"_aaai.out"

#     fp = open(inputFile, "r")
#     lines = fp.readlines()
#     fp.close()

#     dtvs = {}

#     for line in lines:
#         dtvs[line.strip().split(" ")[0]] = float(line.strip().split(" ")[2])

#     if flag == 0:
#         sortedKeys = list(dtvs.keys())
#         sortedKeys.sort()
#         flag += 1

#     dtvs = {i: dtvs[i] for i in sortedKeys}

#     X += list(dtvs.keys())
#     Y += list(dtvs.values())
#     Z += [sampler] * len(dtvs)

# # plt.scatter(X, Y)
# # plt.show()

# mapkeys = {}
# for i in range(len(sortedKeys)):
#     mapkeys[sortedKeys[i]] = i

# for i in range(len(X)):
#     X[i] = mapkeys[X[i]]

# df = pd.DataFrame(list(zip(X, Y, Z)),
#                columns =['Instances', 'Estd TV distance', 'sampler'])
# print(df)
# sns.lineplot(df, x="Instances", y="Estd TV distance", hue="sampler", legend="full", style="sampler", markers=True)
# plt.show()
