#!/bin/bash
#!/usr/bin/python3

FILES="./outDir_aaai/sampler_4*.out"
for FILE in $FILES
do 
	echo $FILE
	python3 dtvfromwgts.py $FILE dtv_cms_aaai.out
done
