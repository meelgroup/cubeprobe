# `CubeProbe`

`CubeProbe` estimates the dtv distance of a sampler from uniform distribution and tests if the sampler is almost uniform or far from uniform. `CubeProbe` achieves the goal by implementing a SubCube Conditioning access to the sampler. 

`CubeProbe` can work in two modes:

1. _Estimator_ mode : In this mode `CubeProbe` returns the estimated total variation distance of the sampler from uniform distribution. 
2. _Tester_ mode : In this mode `CubeProbe` returns 'ACCEPT' if total variation distance is less than tolerance parameter and returns 'REJECT' if total variation distance is more than intolerance parameter. 

Usage:

```python CubeProbe.py --zeta ZETA --eta ETA --epsilon EPSILON --delta DELTA --sampler SAMPLERTYPE --seed SEED --thread THREAD --mode MODE input output```

Here `ZETA` is the approximation parameter for the _Estimator_ mode. `ETA`, `EPSILON` are the farness and closeness paramter in the _Tester_ mode. `DELTA` is confidence parameter. 

`SAMPLERTYPE` accepts 3 values:
- QuickSampler = 1
- STS = 2
- CMSGen = 3
`SEED` has been set to 420 in all the experiments. `THREAD` the is the number of threads used by `CubeProbe`. The arguement `MODE` takes two values:
1. `est` for _Estimator_ mode.
2. `test` for _Tester_ mode.

Corresponding paper available at [here](https://arxiv.org/abs/2312.10999).
