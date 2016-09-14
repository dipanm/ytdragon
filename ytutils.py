
import string

def removeNonAscii(s): return "".join(filter(lambda x: ord(x)<128, s))

# Not allowed characters 
#	filesystem  \ / : * ? " < > | 	other #	@ ? and nonprintable '\t' '\n' '\r'
def pathsafe(s): 
	keepcharacters = (' ','\'','.','_','-','!','%','(',')','+',',',';','[',']','{','}','~')
	return "".join(c for c in s if c.isalnum() or c in keepcharacters).rstrip()

def clean_up_title(title):
	title = title.replace('\n','').strip() 
	title = removeNonAscii(title) 

	printable = set(string.printable)
	title = filter(lambda x: x in printable, title)

	title = pathsafe(title) 

	return title 

def write_to_file(filename,blob): 
	fp = open(filename,"w") 
	if(fp): 
		fp.write(blob) 
		fp.close() 
	return 

