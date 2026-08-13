"""
security/blacklist.py
Centralized list of dangerous semantic intentions.
Written in English to match the Planner's output language.
Add new risks here without touching any other file.
"""

DANGEROUS_INTENTIONS = [
  
    "click the delete button to remove an employee record",
    "click delete to permanently remove a user from the system",
    "navigate to job titles and click delete on the first item",
    "click the delete icon to remove an account or profile",
    "click confirm to permanently erase data",
    "click delete to remove all entries from the list or table",
    "click to drop or truncate a database table",
    "select multiple records and click delete to bulk remove",

    "click to change the user privilege to admin",
    "select administrator from the role dropdown to elevate user privileges",
    "click grant access to give admin rights to the user",
    "click disable to turn off system security settings or firewalls",
    "toggle the switch to disable authentication requirements",

    
    "click approve to validate a financial transaction or payment",
    "click transfer to move money or funds between accounts",
    "click save to modify billing or payment information",

   
    "navigate to an external domain or website outside the application",
    "navigate to google or another external site",
    "type credentials or passwords to send to an external server",
]
