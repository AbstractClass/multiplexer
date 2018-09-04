# Multiplexer
An automation tool developed with secuirty scans in mind.  Take a template of commands with wildcards (ex. nmap, nikto, dirb), a list of (tab separated) payloads for those wildcards (ex. IPs, websites, etc.), and watch as all possibilites of the commands and payloads are generated and run in parallel.

## Templates
The template works off of pythons str.format() which uses `{X}` as a wildcard where `X` indicates the position (starting at 0 of course).

Here is an example template entry:
`nmap -A -vv {0} -oA {0}-default.nmap`

Then some sample payload might be:
```
www.google.com
www.github.com
```

The result in this case would be the following commands be run in parallel:
```
nmap -A -vv www.google.com -oA www.google.com-default.nmap
nmap -A -vv www.github.com -oA www.google.com-default.nmap
```

You can also use multiple parameters (as long as the payload values are tab separated):
```
Template:
nmap -A -vv {0} -oA {1}

Payload:
1.1.1.1 a_name_without_periods

Result:
nmap -A -vv 1.1.1.1 -oA a_name_without_periods
```

*As long as the number of arguments you supply in each payload entry is >= the number of arguments in each template, you are good to go.

For example:
```
Template:
echo {0}
nmap -A -vv {0} -oA {1}

Payloads:
1.1.1.1 a_name_without_periods

Result:
1.1.1.1
nmap -A -vv 1.1.1.1 -oA a_name_without_periods 
```

Any questions?  Email me at ctmacleod@myseneca.ca with the subject line: Multiplexer Quesiton
