import untangle
obj = untangle.parse('config.xml')
#this file defines debug log level with debugflag. 1=errors, 2=verbose
#prints out console lines if debugflag is turned on
debug = obj.root.Application['Debug']
def log1(string):
    if debug >= 1:
        print(string)
def log2(string):
    if debug >= 2:
        print(string)
print('Debug level set to %s' % debug)