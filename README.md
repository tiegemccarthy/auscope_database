Relevant files to generate the first version of the AuScope database. These files contain significant dark magic in order to get 10 years worth of IVS report files (.corr, .skd, spool and analysis reports) to all play nice. 

Running auscope_database_daily.py with an IVS master schedule and SQL database name as the arguments should generate the SQL database -> download files relevant to that master schedule -> scrape information from the files and add to the database. Database is currently hosted on frenkie.phys.utas.edu.au.
