## Steps for creating and testing smart contracts using python

* Setting up and run Algorand Sandbox
	 ```
	 git clone https://github.com/algorand/sandbox.git
	 ```

* Creating and activate python virtual environment
	```
	conda create -n algorandenv python=3.8
	conda activate algorandenv
	pip install py-algorand-sdk pyteal pytest
	```
* If not using sandbox use "goal" tools to start your own node.
	```
	goal node start
	```

