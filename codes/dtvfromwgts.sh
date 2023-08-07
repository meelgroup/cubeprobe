#!/bin/bash
#!/usr/bin/python3

FILES="./outDir/sampler_2*.out"
for FILE in $FILES
do 
	echo $FILE
	python3 dtvfromwgts.py $FILE dtv_sts.out
done
