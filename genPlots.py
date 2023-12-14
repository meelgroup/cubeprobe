import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from statistics import median

samplers = ['quick', 'sts', 'cms']
X, Y, Z = [], [], []
    
# avg dtv or avg nsamples (Y) vs the dimension (X) 
for sampler in samplers:
    inputFile = "./Experiment_1/dtv_"+sampler+"_aaai.out"

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

estddtv = 'Estimated ' + r'$\mathtt{d}_\mathtt{TV}$' + ' distance'
                              
df = pd.DataFrame(list(zip(X, Y, Z)),
               columns =['Dimension', estddtv, 'Samplers'])
print(df)
# sns.scatterplot(df, x="dimension", y="samples", hue="sampler", legend="full")
sns.lineplot(df, x="Dimension", y=estddtv, hue="Samplers", legend="full", style="Samplers", markers=True)
# plt.plot(df["dimension"], df["Estd TV distance"])
plt.show()

