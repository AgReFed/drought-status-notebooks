'''
Run with Python 2.7 (uses raw_input())
Creates 3-factorial Stack (Defaults for CLEM data-cube) and
EITHER appends these to GRASP MRXs (listed in FN_STACK_GEN_MRXLIST)
OR, if no valid FN_STACK_GEN_MRXLIST provided, create the factorial stack
    in a text file (FN_STACK_OUT) to append to the MRX manually.
OPTIONALLY include a Standaridised MRX block (FN_STD_MRX_BLOCK)
    Parameters set to disable dynamic GRASP components for CLEM etc.

Provide a StackGenMRXlist.csv of MRX filenames & changes (can drag&drop):
    Header in line 1 as:
    MRXin, MRXout, StdBlock, p5 GrassBA(%), p194 LandCon, p645 StkRate(hd/km2)
        (parameter numbers in Cols 4-6 are parsed, otherwises uses defaults)
    Input & output filenames in 1st 3 cols
        MRXin - optional, otherwise generate MRX block for appending
        MRXout - name of output modified MRX file (or block for appending)
        StdBlock - optional MRX block text file to include before stack
    Stack specifications in cols 4 onwards (upto Col 6) as:
        space-delimited lists of parameter values in next 3 cols
        OR filename of existing Stack in col 3
        OR Blank (repeat settings of previous file (or defaults for 1st file))
    factorial stack (including std parameter block) will be appended to MRXs.

Can place a comment in input MRXs (see S_APPENED_MARKER) to mark where
    reading of original MRX reading should end
    and where generated new MRX block will be appended.

When a stack is generated, this also creates a StackList.CSV listing the
    parameter settings for each Study in the Stack.

Change the script setting variables below to customise the script

--------------------------------------------------------------------------------
Author: Chris Stokes
--------------------------------------------------------------------------------
#*CHANGELOG ____________________________________________________________________
v1.03: Mar 2021, CS
- Added option to manually specify data-cube factorial on command line
- Converted all deprecated print statements to print() functions (Py3 compliant)

v1.02: Feb 2021, CS
-Updated for use with Cedar GRASP -> CLEM data-cube

v1.01: Jan 2017, CS
- Substantial updates for NAWRA & future ease of use
- Input MRX CSV file now fully specifies details for each modification
    includes retrieving parameter numbers from header
    allows output of modified MRX to a (multiple) different filename
    (or to over-write the original)
- Command line argument for CSV list details file (above)
    allows drag & drop of CSV list onto script
    also allows drag & drop of directory (if CSV list has default name in
    that directory)
-Added Tee-ing of console output to log file
-Improved console logging
- Uses AppendMarkStr to recognise (& ignore) previous blocks added to MRX by
    this script
-PEP8 & Pythonic Style improvements

v1.00: Mar 2015, CS
- FtRG Extensive Grazing project: compare CCCS scenarios
-First version
#TODO __________________________________________________________________________
- xxx
'''


#* ____________________________________________________________________________
#* MODULES_____________________________________________________________________
from __future__ import division  # so int division returns float (use 3//2 for int)
import os  # for getting directory listings of files & calling DOS commands
# import re # for RegExp
import sys
import re
import datetime

#* ____________________________________________________________________________
#* CONFIGURABLE CONSTANTS______________________________________________________

DATA_PATH = r'.'  # use the directory the script runs from for the list of input data

# CSV list of input & output filesnames (cols 1..3) & parameter lists for factorial stack (cols 4..6)
FN_STACK_GEN_MRXLIST = r'StackGenMRXlist.csv'
COMMENT_STR = '#'  # string at start of line that in MRXlist that indicates comment to be ignored

# Default filenames if no valid list is provided in fnStackGenMRXlist
FN_STACK_OUT = r'FactorialMRXStack.txt'  # if no valid list is provided above
FN_STD_MRX_BLOCK = r'CLEM_StdMRXblock_NEXUS.txt'  # r''  # '' to skip, otherwise standardised parameter block (including turning off all dynamic GRASP behaviours for CLEM) to append at end of MRX before stack
FN_STUDIES_OUT = r'StudyList.csv'
FN_LOG = r'StackGen_Log.txt'

# Default initial parameter values if not specified in fnStackGenMRXlist
PARAM_1_NAME = 'GrassBA'
PARAM_1_NUM = 5  # Initial plant density e.g. % grass basal area
L_PARAM_1_VALS = [1, 1.5, 2, 2.5, 3, 4, 5, 6]  # CLEM now handles fractional step changes
PARAM_2_NAME = 'LandCon'
PARAM_2_NUM = 194  # Initial pasture condition 0=90% perennials,11=heavily grazed
L_PARAM_2_VALS = range(0, 12)  # i.e. 0..11
PARAM_3_NAME = 'StkRate'
PARAM_3_NUM = 645  # Hd/km2 stocking rate when p82=13
#PARAM_3_NUM = 83  # OLD Spag -> NABSA stacks | Hd/km2 stocking rate (for p82=13)
#L_PARAM_3_VALS = range(0,7) + range(8,20,2) + range(20,51,5)  # hd/km2  (NOTE conversion: 1hd/100ha = 1hd/km2, and that CEDAR output <ae_beast_ha> is in AE/ha)
L_PARAM_3_VALS = range(1, 71)  # i.e. 1..10 hd/km2  (NOTE conversion: 1hd/100ha = 1hd/km2)
#* Small test factorial
#L_PARAM_1_VALS = [1, 2, 3, 5]
#L_PARAM_2_VALS = [0, 3, 6, 9, 11]
#L_PARAM_3_VALS = [2, 5, 10, 20, 40, 80]  # Growth within a season is not very senstive to StkRate in GRASP (and when feedbacks on LandCon and GrassBA are disabled)

# comment marking start of stack in MRX (will be indented (as per MRX comment requirements), preceded by line of '_'s and followed by sStackSpecs )
S_STACK_START_COMMENT = '#CLEM DATA-CUBE FACTORIAL STACK: {} (p{}) x {} (p{}) x {} (p{})'.format(PARAM_1_NAME, PARAM_1_NUM, PARAM_2_NAME, PARAM_2_NUM, PARAM_3_NAME, PARAM_3_NUM)

FN_MRX_TEMP = 'MRXtemp.txt'  # temporary file to use if input & output files are the same
S_APPENED_MARKER = '_________ APPENDED BY STACKGEN.PY _________'  # string marking start of block appended by this script - used to recognise (& not duplicate) this block again
#S_STACK_MARKER = '_____ Stack: Factorial Parameter Combinations _____'  # string marking start of Stack appended by this script
# rxAppendMarker = re.compile(r'\s+_+\.*append.*stackgen.*_+.*', re.IGNORECASE)
#RX_REPLACE_MARKER = re.compile(r'\s+_+.*stack.*_+.*', re.IGNORECASE)  # matches both Append & Stack Markers
RX_REPLACE_MARKER = re.compile(r'\s+' + S_APPENED_MARKER, re.IGNORECASE)  # matches both Append Markers

S_MRX_COMMENT_INDENT = ' ' * 13  # space padding to indent comments in MRX files

B_PROMPT_FOR_STACK_FACTORIAL = True  # prompt for manually entering default stack dimensions (used if factorial not provided in SimList)

#* ____________________________________________________________________________
#* FUNCTIONS & OBJECTS_________________________________________________________

class Tee:
    """Allows output (stdout or stderr) to be redirected to BOTH console & a log file
    from: http://www.shallowsky.com/blog/programming/python-tee.html
    The solution is to use composition rather than inheritance. Don't make your
    file-like class inherit from file, but instead include a file object inside it.
    usage example, insert the code below into the main script:
        stdoutsav = sys.stdout
        outputlog = open('log.txt', "w")
        sys.stdout = tee(stdoutsav, outputlog)"""
    def __init__(self, _fd1, _fd2):
        self.fd1 = _fd1
        self.fd2 = _fd2

    def __del__(self):
        if self.fd1 != sys.stdout and self.fd1 != sys.stderr:
            self.fd1.close()
        if self.fd2 != sys.stdout and self.fd2 != sys.stderr:
            self.fd2.close()

    def write(self, text):
        self.fd1.write(text)
        self.fd2.write(text)

    def flush(self):
        self.fd1.flush()
        self.fd2.flush()


def filtered_dir_list(path, list_reg_exp_pattern_str):
    """Returns a directory list of 'Path', selecting only those files that match the list of RegExp patterns provided"""
    dir_list = []
    for reg_exp_pattern_str in list_reg_exp_pattern_str:
        dir_list.extend([f for f in os.listdir(path)
                if re.match(reg_exp_pattern_str, f, re.I)])
    return dir_list

#* ____________________________________________________________________________
#* MAIN CODE___________________________________________________________________

print

# Get command line arguments
if (len(sys.argv) > 1):
    arg1 = sys.argv[1]
#     arg1 could be either a directory or a filename
    if os.path.isdir(arg1):
        DATA_PATH = arg1
    else:
        DATA_PATH, FN_STACK_GEN_MRXLIST = os.path.split(arg1)
        if DATA_PATH == '':
            DATA_PATH = '.'

os.chdir(DATA_PATH)  # set working dir

# 'Tee' (duplicate) all console output to BOTH screen and log file
fLog = open(FN_LOG, 'w')
StdOutSav = sys.stdout
TeeOut = Tee(StdOutSav, fLog)
sys.stdout = TeeOut

# script details
print(datetime.datetime.now().strftime('%a %d %b %Y %H:%M:%S'))
fnScript = os.path.basename(__file__)
sTimeStampFile = datetime.datetime.fromtimestamp(os.path.getmtime(fnScript)).strftime('%Y-%m-%d %H:%M:%S')
print('   Script       : {}    ({})'.format(fnScript, sTimeStampFile))  # name of this script file
print('   Data path    : {}'.format(os.getcwd()))
if os.path.isfile(FN_STACK_GEN_MRXLIST):
    sTimeStampFile = datetime.datetime.fromtimestamp(os.path.getmtime(FN_STACK_GEN_MRXLIST)).strftime('%Y-%m-%d %H:%M:%S')
    print('   StackGen List: {}    ({})'.format(FN_STACK_GEN_MRXLIST, sTimeStampFile))
else:
    print('   No valid StackGen List provided.')
print('')

print("\nDefault data-cube stack factorial: {} x {} x {} = {} MRX 'Studies'".format(len(L_PARAM_1_VALS), len(L_PARAM_2_VALS), len(L_PARAM_3_VALS),len(L_PARAM_1_VALS) * len(L_PARAM_2_VALS) * len(L_PARAM_3_VALS)))
print('     {:9s}: {}\n     {:9s}: {}\n     {:9s}: {}\n'.format(PARAM_1_NAME, L_PARAM_1_VALS, PARAM_2_NAME, L_PARAM_2_VALS, PARAM_3_NAME, L_PARAM_3_VALS))

if B_PROMPT_FOR_STACK_FACTORIAL:
    sOpt = input('\nType:\n    "m" to manually enter a new stack factorial,\n    "q" to quit,\n    any other key to accept and continue\n> ').strip().lower()[:1]
    print('\n')
    if sOpt == 'q':
        print('\n\nQuit without processing files\n')
        sys.exit()
    elif sOpt == 'm':
        # Sequence of prompts for user to manually specificy all filtering options
        # GrassBA
        sOpt2 = input('{}: enter a comma(or-space)-delimited set of values (or <Enter> to keep defaults above)\n    >'.format(PARAM_1_NAME)).strip().lower()
        if sOpt2 != '':
            try:
                L_PARAM_1_VALS = [float(s) for s in re.split('s*[,\s]\s*', sOpt2)]
            except:
                print('Invalid list of numbers provided (e.g., should be <1,5,9.5> without "<>" markers):\n<{}>\n'.format(sOpt2))
                sys.exit()
        # StkRate
        sOpt2 = input('{}: enter a comma(or-space)-delimited set of values (or <Enter> to keep defaults above)\n    >'.format(PARAM_2_NAME)).strip().lower()
        if sOpt2 != '':
            try:
                L_PARAM_2_VALS = [float(s) for s in re.split('s*[,\s]\s*', sOpt2)]
            except:
                print('Invalid list of numbers provided (e.g., should be <1,5,9.5> without "<>" markers):\n<{}>\n'.format(sOpt2))
                sys.exit()
        # LandCon
        sOpt2 = input('{}: enter a comma(or-space)-delimited set of values (or <Enter> to keep defaults above)\n    >'.format(PARAM_3_NAME)).strip().lower()
        if sOpt2 != '':
            try:
                L_PARAM_3_VALS = [float(s) for s in re.split('s*[,\s]\s*', sOpt2)]
            except:
                print('Invalid list of numbers provided (e.g., should be <1,5,9.5> without "<>" markers):\n<{}>\n'.format(sOpt2))
                sys.exit()


# ----------------------------------------------------------------------------
# Get a list of MRX files to modify (by appending stack generated above)
# CSV file with 6 columns: MRXin, MRXout, StdBlock, p5_list, p194_list, p83_list (lists space-delimited)
lStackGen = []
if os.path.isfile(FN_STACK_GEN_MRXLIST):
    # print('-' * 20)
    print('Getting List of MRX files and modification settings to generate new versions with generated stacks.')
    with open(FN_STACK_GEN_MRXLIST) as fMRXcsv:
        # Read header in first line
        line = fMRXcsv.next()
        lParamHeaders = []
        # Try to parse the 3 parameter numbers for the factorial stack from cols/fields 4-6
        try:
            lParamHeaders = [s for s in line.split(',')[3:6]]
            for i, s in enumerate(lParamHeaders):
                m = re.match(r'.*p(\d+).*', s, re.I)
                if m:
                    lParamHeaders[i] = int(m.group(1))
                    if lParamHeaders[i] < 1 or lParamHeaders[i] > 999:  # valid parameter numbers are integers 0 < n < 1000
                        raise ValueError()
                else:
                    raise ValueError()
            Var1ParamNum, Var2ParamNum, Var3ParamNum = lParamHeaders
            print('Parameters specified for 3-factorial stacks (extracted from HEADER): p{}, p{}, p{}'.format(Var1ParamNum, Var2ParamNum, Var3ParamNum))
        except:
            Var1ParamNum, Var2ParamNum, Var3ParamNum = PARAM_1_NUM, PARAM_2_NUM, PARAM_3_NUM
            print('!!Could NOT extract valid parameter numbers from header, using DEFAULT 3 Parameters: p{}, p{}, p{}'.format(Var1ParamNum, Var2ParamNum, Var3ParamNum))
            print(lParamHeaders)
        # Read details of Stacks & StdBlocks to be added to each MRX
        for line in fMRXcsv:
            line = line.strip()
            if line.strip('\t\n ",') == '':  # skip blank lines
                continue
            if line.strip('\t\n ",')[:len(COMMENT_STR)] == COMMENT_STR:  # print comments, then skip
                print('    ' + line.strip(',"'))
                continue
            # Get and check the expected 6 fields (padded & truncated to 6 exactly)
            fields = [t.strip('\t\n "') for t in line.split(',')]
            fields = (fields + [''] * 6)[:6]  # 6 fields expected, set default for missing fields
            fnMRXin, fnMRXout, fnStdMrxBlock, Var1, Var2, Var3 = fields
            # Input & Output filenames in 1st 3 Cols
            if not(os.path.isfile(fnMRXin) or fnMRXin == ''):
                print('  xx> {} < MRXin does not exist - SKIPPED'.format(fnMRXin))
                continue
            elif not(os.path.isfile(fnStdMrxBlock) or fnStdMrxBlock == ''):
                print('  xx> {} < StdBlock does not exist - SKIPPED'.format(fnStdMrxBlock))
                continue
            # Stack settings are in Cols 4-6
            if not Var1:  # blank value = repeat previous Stack settings
                pass
            elif not Var2:  # Filename of existing Stack provided in Var1, Var2 is empty - Stack could be generated as preceding entry, so can't check yet
                pass
            elif not Var3:  # if Var1 & 2 are provided, then Var is expected
                print('  xx>{}|{}|{}< Invalid/Incomplete Stack settings - SKIPPED'.format(*fields[3:6]))
                continue
            elif Var3:  # Var1-3 should be 3 space-delimited sets of parameter values
                # check all 3 lists of parameter values are valid
                try:
                    for i, s in enumerate(fields[3:6], start=3):
                        ParamList = s.split()  # list of STRINGS (not numbers)
                        if not ParamList:
                            raise(ValueError)  # list of values cannot be empty
                        for t in ParamList:
                            float(t)  # test that strings represent valid numbers
                        fields[i] = ParamList
                except:
                    print('  xx>{}|{}|{}< Invalid Stack Parameter lists - SKIPPED'.format(*fields[3:6]))
                    print(ParamList)
                    continue
            # Settings have passed all checks - add them to list of MRXs to generate
            lStackGen.append(fields)
            print('{:6d}. "{}" + "{}" -> "{}"'.format(len(lStackGen), fnMRXin, fnStdMrxBlock, fnMRXout))

if lStackGen:
    print('Valid list of StackGen mods provided.')
else:
    # sys.exit('\nNo valid MRX list provided, Stack NOT appedend to MRX(s)\n')
    print('\n!!NO valid StackGen list provided, creating Stack File using DEFAULTs - Append this MANUALLY yourself if wanted')
    Var1ParamNum, Var2ParamNum, Var3ParamNum = PARAM_1_NUM, PARAM_2_NUM, PARAM_3_NUM
    lStackGen = [['', FN_STACK_OUT, FN_STD_MRX_BLOCK, L_PARAM_1_VALS, L_PARAM_2_VALS, L_PARAM_3_VALS]]  # use defaults (without appending to any base MRX)

# ----------------------------------------------------------------------------------------------------------------------
# Append Stacks (& Std Blocks) to MRXs
NumMRXs = len(lStackGen)
fnStack = 'not assigned yet'
lVar1Vals, lVar2Vals, lVar3Vals = '', '', ''
# Process each MRX in list, generating new version with stack
print('\nGenerating and Appending Factorial Stacks to MRXs:')
print('(        MRXout = MRXin + StdBlock + 3-Factorial Stack from parameter lists)')
print('-' * 80)
for i, (fnMRXin, fnMRXout, fnStdMrxBlock, Var1, Var2, Var3) in enumerate(lStackGen, start=1):
    # Apply Stack settings for generating new MRX
    if i == 1 and not Var3:
        # Set Stack Defaults for 1st file, if no Stack details are specified
        lVar1Vals, lVar2Vals, lVar3Vals = L_PARAM_1_VALS, L_PARAM_2_VALS, L_PARAM_3_VALS
        bAppendStackFile = False
        #sStackSpecs = 'p{}[{}] * p{}[{}] * p{}[{}]'.format(Var1ParamNum, ' '.join([str(k) for k in lVar1Vals]), Var2ParamNum, ' '.join([str(k) for k in lVar2Vals]), Var3ParamNum, ' '.join([str(k) for k in lVar3Vals]))
        sStackSpecs = 'p{}[{}]{} * p{}[{}]{} * p{}[{}]{} = {}'.format(  Var1ParamNum, ' '.join([str(k) for k in lVar1Vals]), len(lVar1Vals), \
                                                                        Var2ParamNum, ' '.join([str(k) for k in lVar2Vals]), len(lVar2Vals), \
                                                                        Var3ParamNum, ' '.join([str(k) for k in lVar3Vals]), len(lVar3Vals), \
                                                                        len(lVar1Vals) * len(lVar2Vals) * len(lVar3Vals))
    elif not Var1 or (Var1, Var2, Var3) == (lVar1Vals, lVar2Vals, lVar3Vals):
        # Settings are the same as previous file - no need to change anything
        sStackSpecs = '     Stack as above'
    elif (type(Var1), type(Var2), type(Var3)) == (list, list, list):
        # Lists of parameter values provided for generating 3-factorial stack
        bAppendStackFile = False
        lVar1Vals, lVar2Vals, lVar3Vals = Var1, Var2, Var3
        #sStackSpecs = 'p{}[{}] * p{}[{}] * p{}[{}]'.format(Var1ParamNum, ' '.join([str(k) for k in lVar1Vals]), Var2ParamNum, ' '.join([str(k) for k in lVar2Vals]), Var3ParamNum, ' '.join([str(k) for k in lVar3Vals]))
        sStackSpecs = 'p{}[{}]{} * p{}[{}]{} * p{}[{}]{} = {}'.format(  Var1ParamNum, ' '.join([str(k) for k in lVar1Vals]), len(lVar1Vals), \
                                                                        Var2ParamNum, ' '.join([str(k) for k in lVar2Vals]), len(lVar2Vals), \
                                                                        Var3ParamNum, ' '.join([str(k) for k in lVar3Vals]), len(lVar3Vals), \
                                                                        len(lVar1Vals) * len(lVar2Vals) * len(lVar3Vals))
    elif type(Var1) in (unicode, str) and os.path.isfile(Var1):
        # Filename of existing stack provided
        bAppendStackFile = True
        fnStack = Var1
        sStackSpecs = '"{}"'.format(fnStack)  # put the string in double quotes
    else:
        print('!! {} /{}:Invalid Stack settings, SKIPPED: "{}" = "{}" + "{}" + !!{} {} {}!!'.format(i, NumMRXs, fnMRXout, fnMRXin, fnStdMrxBlock, Var1, Var2, Var3))
        continue

    # Generate the new, modified MRX
    print('{:4d} /{}: "{}" = "{}" + "{}" + {}'.format(i, NumMRXs, fnMRXout, fnMRXin, fnStdMrxBlock, sStackSpecs))
    # If Input & Output MRX are the same, use a temporary output file, then rename
    if fnMRXin == fnMRXout:
        fnOut = FN_MRX_TEMP
    else:
        fnOut = fnMRXout
    # Build the new file, adding components sequentially
    with open(fnOut, 'w') as fMRXout:
        # Start with the base input MRX (IF specified)
        if fnMRXin:
            sTimeStampMRXin = datetime.datetime.fromtimestamp(os.path.getmtime(fnMRXin)).strftime('%Y-%m-%d %H:%M:%S')
            sMRXinDescr = 'based on: {} ({})'.format(fnMRXin, sTimeStampMRXin)
            with open(fnMRXin, 'r') as fMRXin:
                for line in fMRXin:
                    if RX_REPLACE_MARKER.match(line):  # Marks a previous block or stack added to MRX by this script
                        break
                    if line[:3] == '300':  # The first occurrence of Parameter 300 marks the end of the main MRX file (and each stack subsequently)
                        break
                    fMRXout.write(line)
        else:
            sMRXinDescr = 'for manual appending'
        # Mark start of appended block (for reference & so it can be found/ignored by this script in future)
        fMRXout.write('\n             {} (generated {}) {}\n'.format(S_APPENED_MARKER, datetime.datetime.now().strftime('%a %d %b %Y %H:%M:%S'), sMRXinDescr))
        # Append Standard MRX block (IF specified)
        if fnStdMrxBlock:
            if os.path.isfile(fnStdMrxBlock):
                try:
                    with open(fnStdMrxBlock, 'r') as fStd:
                        for line in fStd:
                            if line[:3] == '300':  # The first occurrence of Parameter 300 marks the end of the main MRX file (and each stack subsequently)
                                break
                            fMRXout.write(line)
                except:
                    print('!ERROR trying to append Standard MRX Block <{}> - continuing without appending file - check output file <{}>!'.format(fnStdMrxBlock, fnMRXout))
            else:
                print('!ERROR Standard MRX Block <{}> does not exist - continuing without appending file - check output file <{}>!'.format(fnStdMrxBlock, fnMRXout))
        # Append Stack (2 options)
        if bAppendStackFile:
            # Append existing Stack File
            with open(fnStack, 'r') as fStk:
                for line in fStk:
                    fMRXout.write(line)
        else:
            # Generate 3-factorial stack from parameter lists (also create a CSV list with details of each 'Study' in the Stack)
            with open(FN_STUDIES_OUT, 'w') as fStudiesOut:
                # write header for Studies List
                fStudiesOut.write('StudyNo,p{:03d},p{:03d},p{:03d}\n'.format(Var1ParamNum, Var2ParamNum, Var3ParamNum))
                StudyNo = 0
                # Mark start of Stack block (1st Study in Stack is the main, 1st pass of the MRX)
                sStackDimensions = 'p{}[{}]{} * p{}[{}]{} * p{}[{}]{} = {}'.format( Var1ParamNum, ' '.join([str(k) for k in lVar1Vals]), len(lVar1Vals), \
                                                                                    Var2ParamNum, ' '.join([str(k) for k in lVar2Vals]), len(lVar2Vals), \
                                                                                    Var3ParamNum, ' '.join([str(k) for k in lVar3Vals]), len(lVar3Vals), \
                                                                                    len(lVar1Vals) * len(lVar2Vals) * len(lVar3Vals))
                fMRXout.write(S_MRX_COMMENT_INDENT + '_' * 73 + '\n')
                fMRXout.write(S_MRX_COMMENT_INDENT + S_STACK_START_COMMENT + '\n')
                fMRXout.write(S_MRX_COMMENT_INDENT + sStackDimensions + '\n')
                for v1 in lVar1Vals:
                    for v2 in lVar2Vals:
                        for v3 in lVar3Vals:
                            # Create an individual Study/Stack entry from a unique combination of the 3 parameters
                            StudyNo += 1
                            # Study title - NOTE: used for SPAGHETTI GRASP as a reliable way of passing the stack variables to output files
                            sTitle = 'Study{:4d}: p{:03d}= {}, p{:03d}= {}, p{:03d}= {}'.format(StudyNo, Var1ParamNum, v1, Var2ParamNum, v2, Var3ParamNum, v3)
                            # skip the initial stack title for the first run
                            if StudyNo == 1:
                                fMRXout.write(S_MRX_COMMENT_INDENT + 'Study 1: 1st Stack item is the inital base MRX run ----------\n')
                            else:
                                fMRXout.write(sTitle + ' ----------\n')
                            fMRXout.write('{:03d} {}\n'.format(Var1ParamNum, v1))
                            fMRXout.write('{:03d} {}\n'.format(Var2ParamNum, v2))
                            fMRXout.write('{:03d} {}\n'.format(Var3ParamNum, v3))
                            fMRXout.write('300       0.00 End of parameters\n')
                            fMRXout.write(sTitle + '\n')
                            fMRXout.write('file end  99990000  for GRASP\n')
                            # Parameter combinations for each study output to StudyList CSV file
                            fStudiesOut.write('{},{},{},{}\n'.format(StudyNo, v1, v2, v3))
                            sys.stdout = StdOutSav  # pause logging for console progress logging of each study
                            sys.stdout.write(' ' * 9 + sTitle + '\r')  # Add '\r' to keep updating same line
                            sys.stdout = TeeOut
                sys.stdout = StdOutSav  # pause logging - fixing use of '\r' directed to console (NOT Teed) progress above
                print('')  # end of '\r' printing, move to next line
                sys.stdout = TeeOut
    # rename files
    if fnMRXin == fnMRXout:
        if os.path.isfile(fnMRXin + '.bak'):
            os.remove(fnMRXin + '.bak')
        os.rename(fnMRXin, fnMRXin + '.bak')
        os.rename(FN_MRX_TEMP, fnMRXin)


# Clean up & finish
# print('')
print('-' * 80)
print (datetime.datetime.now().strftime('%a %d %b %Y %H:%M:%S'))
print('\nList of parameters for each Study in Stack: {} (for last Stack generated above)'.format(FN_STUDIES_OUT))
print('MRX factorial stack in: {}'.format(FN_STACK_OUT))
print('Log of console output in: {}'.format(FN_LOG))

sys.stdout = StdOutSav
del(TeeOut)
# fLog.close()

# if script was run by drag-and-drop, then pause to keep CMD Shell window open
# if (len(sys.argv) > 1):
os.system('pause')
