# Opportunity

This is the repository for an app designed to help people find their next steps in life--whether it be graduate school, potential jobs, gap year programs, etc. 

The concept is that the user will provide context to the app, which will scrape backend logs of opportunities and the internet for tailored recommendations. 

The difficulty is building an algorithm that can accurately synthesize the training information, as well as know where to look on the internet for recommendations. 

parts that need to be ironed out:

-workflow: integration with claude, github issues, etc. 

-structure: is this a webapp? How do we setup the server? Should the service be local only and downloaded by the user? Should the user be providing longform text, questionaire, resume, or a mixture? Should we currate a baseline level of common opportunities in a dataset that the model can match to leanly?

-optimization: how do we optimize the results? What are the best things to ask the user to provide for training? what do we need to tell the scraper to look at in particular (eg. weighing twitter as opposed to google search)? Surely, issues can arise if the user provides TOO much information to the bot. Compute optimization. 

-misc: should there be multiple algorithms trained for different use-cases? ie. grad school programs, potential jobs, gap years, travel destinations? Determining the level of the user: not all users are going to be candidates for the Rhodes Scholarship; need to find a way to evaluate the user and recommend achievable outcomes. 

will need to do rigorous testing with profiles of many backgrounds to decide the best results... how do we even begin to measure what the "best" results are? 
