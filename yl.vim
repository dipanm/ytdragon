syntax match ylcomment 	/#.*$/
syntax match yldone 	/^@.*$/
syntax match ylerror 	/^?.*$/
syntax match ylcmd 	/^=.*$/
highlight ylcomment 	ctermfg=darkblue
highlight yldone 	ctermfg=green
highlight ylerror 	ctermfg=red
highlight ylcmd 	ctermfg=yellow
