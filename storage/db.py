"""Set up SQLAlchemy for mySQL database connection"""

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load db variables
with open("config/storage.prod.yaml", "r", encoding="utf-8") as f:
    db_config = yaml.safe_load(f.read())

# Set up an engine
engine = create_engine(
    f"mysql://{db_config['datastore']['user']}:{db_config['datastore']['password']}"
    f"@{db_config['datastore']['hostname']}/{db_config['datastore']['db']}"
)


# Factory function to get a session bound to the DB engine
def make_session():
    return sessionmaker(bind=engine)()
