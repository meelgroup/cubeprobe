#!/bin/bash
#!/usr/bin/python3

FILES="./outDir/*.out"
for FILE in $FILES
do 
	echo $FILE
	python3 dtvfromwgts.py $FILE dtv.out
done
