from feedfounders.app import db

# Create the database and the database table

db.create_all()

# Commit the changes
db.session.commit()
