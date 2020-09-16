Relevant files to generate the first version of the AuScope database. These files contain significant dark magic in order to get 10 years worth of IVS report files (.corr, .skd, spool and analysis reports) to all play nice. 

Running auscopeDB_daily.py with an IVS master schedule and SQL database name as the arguments should generate the SQL database -> download files relevant to that master schedule -> scrape information from the files and add to the database. Database is currently hosted on frenkie.phys.utas.edu.au.

Files in this repo should be all that is required in order to get the database up and running. Crontab entries should be made if you want the scripts to scrape latest reports from the IVS servers daily. Also, the weeklylog.sh script should be given a weekly cron job in order to keep weekly log files of whats been added to the DB and email the latest weekly log.
