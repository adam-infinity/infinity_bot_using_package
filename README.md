# README #

This *infinity_python_demo* code comes with no guarantees but is provided as-is only, in order to assist other users 
quickly get up to speed with our Infinity APIs.

### Installation ###

* This sample code is written in python.
* Please see the *requirements.txt* file to know which python library versions are required.
(See *Dockerfile* for more info.)

### Setting up Configuration & Environment Variables ###

* Add your public wallet address to *config.yml* and your private wallet key to the *.env* file.
* Also in *config.yml* you can specify other bot related parameters including which tokens and markets to trade, and 
maximum order size etc.

### (IMPORTANT) Troubleshooting ###

* Once all the python libraries are installed, if you try to run the code, you will likely encounter the following error:
*cannot import name 'getargspec' from 'inspect'*
* A quick fix to resolving this error is to replace *from inspect import getargspec* with 
*from inspect import getfullargspec* in the related expressions.py file. (See *Dockerfile* for more info.)

### Code Logic ###

* To run the code, run *main.py* in the root directory.
* For each bot described in *config.yml* (e.g. bot_main), a *ParentBot* instance is created.
* Within each bot (i.e. within each *ParentBot* instance), a separate *TokenBot* instance is created for each token/market 
pair.
* A separate, single *InfinityApiBot* instance is also run to handle market data API calls and keep track of the latest
market data.

### Code Structure ###

* The root directory contains *Dockerfile*, *main.py*, *README.md*, *requirements.txt* and helper files *.dockerignore*
and *.gitignore*
* The *bot_params* folder contains the class *TokenParams* for checking that parameters are correctly passed to
*TokenBot.*
* The *bots* folder contains the three instance types that run on their own threads - *InfinityApiBot*, *ParentBot* and
*TokenBot*.
* The *constants* folder contains various constants used by the code and our Infinity protocol.
* The *logs* folder stores daily logs (if enabled in the *config.yml* file).
* The *misc* folder contains the *config.yml* file and also a *.env* file. (As mentioned above, your public wallet 
address should go into *config.yml* and your private wallet key should go into the *.env* file.)
* The *other* folder contains two helper sets of functions. *InfinityAPIHandler* makes the actual API calls to the 
Infinity servers. *MiscHelperFunctions* contains all other helper functions.