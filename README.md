# SIMPLE INVESTING - portfolio comparison tool
#### Video Demo:  <URL HERE>
#### Description:
**TODO** - should at least be several hundred words that describe things in detail! 750 words is likely to be sufficient???

I have developed a Flask App that aims at promotion of low-cost, low-maintans, long-term investing (Boggleheads style). My app's main feature is a table which displays long term returns of chosen etfs based portfolios over 5, 10, 20 and 30 years periods. A comparison table is fed with extended historical data (enhaced with corresponding indexes and simulations) and up to date thanks to monthly performed updates from two independent data sources.

##### **Step-by-step - Process explained**

1. App is set to fetch data (etfs prices) from two different online sources (one via API, one via library).
2. A db table storing historical prices is appended with new data. To reach 30 years history Ihave extanded etfs historical returns with indexes data and at some cases simulated results based od avarage long term returns.
3. Etfs annual yeilds are computed and updated in the db.
4.

##### **Re 1:**

This process is triggered once on a startup and than once a month via scheduler (monthly data is used). When data from both sources is available it's using the avarage of both. Whole process runs only if: 1) data for previous month isn't already present in the db, or 2) it's not the first day of the month and data might not be available yet.

I have considered adding a mechanism checking db for needed update further back in time but as the app is intended to run on the server all the time and in event of failer would be soon restarted, I dropped it as unneeded.

Re 2
The portfolio comperison tool (= index page table) displays data from the database.

# SPRAWDŹ czy dobry angielski ???!!!
