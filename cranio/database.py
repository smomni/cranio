import enum
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (Column, Integer, String, DateTime, Float, Boolean, Enum, ForeignKey, create_engine,
                        CheckConstraint)
from cranio.core import generate_unique_id, timestamp
from cranio import __version__

# define database connection
db_engine = None
Base = declarative_base()
SQLSession = sessionmaker()


def init_database(engine_str: str='sqlite://'):
    global db_engine
    db_engine = create_engine(engine_str)
    # create all databases
    Base.metadata.create_all(db_engine)


@contextmanager
def session_scope(engine=None):
    ''' Provide a transactional scope around a series of operations. '''
    if engine is None:
        # use global db_engine by default
        engine = db_engine
    SQLSession.configure(bind=engine)
    session = SQLSession()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


class Patient(Base):
    __tablename__ = 'dim_patient'
    patient_id = Column(String, CheckConstraint('patient_id != ""'), primary_key=True,
                        comment='Patient identifier (pseudonym)')
    created_at = Column(DateTime, default=timestamp, comment='Patient creation date and time')


class Session(Base):
    __tablename__ = 'dim_session'
    session_id = Column(String, primary_key=True, default=generate_unique_id,
                comment='Autogenerated session identifier (UUID v1)')
    patient_id = Column(String, ForeignKey('dim_patient.patient_id'), nullable=False)
    started_at = Column(DateTime, comment='Session start (i.e., software launch) date and time')
    sw_version = Column(String, default=__version__)


class Document(Base):
    __tablename__ = 'dim_document'
    document_id = Column(String, primary_key=True, default=generate_unique_id,
                comment='Autogenerated document identifier (UUID v1)')
    session_id = Column(String, ForeignKey('dim_session.session_id'), nullable=False)
    distractor_id = Column(Integer, comment='Distractor identifier (e.g., 1 or 2)')
    started_at = Column(DateTime, comment='Data collection start date and time')
    operator = Column(String, comment='Person responsible for the distraction')
    notes = Column(String, comment='User notes')
    distraction_achieved = Column(Float, comment='Achieved distraction in millimeters')
    missed_distractors = Column(String, comment='Comma-separated list of missed distractor identifiers')
    distraction_plan_followed = Column(Boolean, comment='Boolean indicating if the distraction plan was followed')


class Measurement(Base):
    __tablename__ = 'fact_measurement'
    measurement_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey('dim_document.document_id'), nullable=False)
    time_s = Column(Float, nullable=False, comment='Time since start of data collection in seconds')
    torque_Nm = Column(Float, nullable=False, comment='Torque measured from the screwdriver')
    event_id = Column(Float, nullable=True, comment='Manually annotated distraction event identifier')


class LogLevel(enum.Enum):
    DEBUG = 0
    INFO = 1
    ERROR = 2


class Log(Base):
    ''' Software log table '''
    __tablename__ = 'fact_log'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey('dim_document.document_id'))
    created_at = Column(DateTime, nullable=False, comment='Log entry date and time')
    logger = Column(String, nullable=False, comment='Name of the logger')
    level = Column(Enum(LogLevel), nullable=False, comment='Log entry level')
    trace = Column(String, comment='Error traceback')
    message = Column(String, nullable=False, comment='Log entry')


def export_schema_graph(name: str):
    '''
    Export schema graph as a .png image.
    NOTE: Requires Graphviz (download from http://www.graphviz.org/download/)
    '''
    from sqlalchemy_schemadisplay import create_schema_graph
    graph = create_schema_graph(metadata=Base.metadata, show_datatypes=False, show_indexes=False,
                                rankdir='TB', concentrate=False)
    graph.write_png(name)
