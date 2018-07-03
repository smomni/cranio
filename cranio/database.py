from contextlib import contextmanager, closing
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (Column, Integer, String, DateTime, Numeric, Boolean, ForeignKey, create_engine,
                        CheckConstraint, event)
from cranio.core import generate_unique_id, timestamp
from cranio.utils import get_logging_levels
from cranio import __version__

# define database connection
db_engine = None
Base = declarative_base()
SQLSession = sessionmaker()


def _fk_pragma_on_connect(dbapi_con, con_record):
    ''' Enforce sqlite foreign keys '''
    dbapi_con.execute('pragma foreign_keys=ON')


def get_engine():
    return db_engine


def init_database(engine_str: str='sqlite://'):
    global db_engine
    db_engine = create_engine(engine_str)
    # enforce sqlite foreign keys
    event.listen(db_engine, 'connect', _fk_pragma_on_connect)
    # create all databases
    Base.metadata.create_all(db_engine)
    # populate lookup tables
    with session_scope() as s:
        # log levels
        for level, level_name in get_logging_levels().items():
            s.add(LogLevel(level=level, level_name=level_name))
        # event types
        for obj in EVENT_TYPES:
            s.add(EventType(event_type=obj.event_type, event_type_description=obj.event_type_description))


def clear_database():
    """
    Truncate all database tables

    :return:
    """
    with closing(get_engine().connect()) as con:
        trans = con.begin()
        for table in reversed(Base.metadata.sorted_tables):
            con.execute(table.delete())
        trans.commit()


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


class InstanceBase:

    @classmethod
    def reset_instance(cls):
        cls.instance_id = None


class Patient(Base, InstanceBase):
    __tablename__ = 'dim_patient'
    patient_id = Column(String, CheckConstraint('patient_id != ""'), primary_key=True,
                        comment='Patient identifier (pseudonym)')
    created_at = Column(DateTime, default=timestamp, comment='Patient creation date and time')
    # global instance
    instance_id = None

    @classmethod
    def init(cls, patient_id) -> str:
        if cls.instance_id is not None:
            raise ValueError('{} already initialized'.format(cls.__name__))
        with session_scope() as s:
            s.add(cls(patient_id=patient_id))
            cls.instance_id = patient_id
        return cls.instance_id


class Session(Base, InstanceBase):
    __tablename__ = 'dim_session'
    session_id = Column(String, primary_key=True, default=generate_unique_id,
                comment='Autogenerated session identifier (UUID v1)')
    started_at = Column(DateTime, comment='Session start (i.e., software launch) date and time')
    sw_version = Column(String, default=__version__)
    # global instance
    instance_id = None

    @classmethod
    def init(cls) -> str:
        if cls.instance_id is not None:
            raise ValueError('{} already initialized'.format(cls.__name__))
        with session_scope() as s:
            obj = cls()
            s.add(obj)
            s.flush()
            cls.instance_id = obj.session_id
        return cls.instance_id


class Document(Base, InstanceBase):
    __tablename__ = 'dim_document'
    document_id = Column(String, primary_key=True, default=generate_unique_id,
                comment='Autogenerated document identifier (UUID v1)')
    session_id = Column(String, ForeignKey('dim_session.session_id'), nullable=False)
    patient_id = Column(String, ForeignKey('dim_patient.patient_id'), nullable=False)
    distractor_id = Column(Integer, comment='Distractor identifier (e.g., 1 or 2)')
    started_at = Column(DateTime, comment='Data collection start date and time')
    operator = Column(String, comment='Person responsible for the distraction')
    notes = Column(String, comment='User notes')
    distraction_achieved = Column(Numeric, comment='Achieved distraction in millimeters')
    missed_distractors = Column(String, comment='Comma-separated list of missed distractor identifiers')
    distraction_plan_followed = Column(Boolean, comment='Boolean indicating if the distraction plan was followed')
    # global instance
    instance_id = None

    @classmethod
    def init(cls, patient_id=None) -> str:
        if cls.instance_id is not None:
            raise ValueError('{} already initialized'.format(cls.__name__))
        if patient_id is None:
            patient_id = Patient.instance_id
        if Session.instance_id is None:
            raise ValueError('Session must be initialized before Document')
        if patient_id is None:
            raise ValueError('Patient must be initialized before Document')
        with session_scope() as s:
            obj = cls(session_id=Session.instance_id, patient_id=patient_id)
            s.add(obj)
            s.flush()
            cls.instance_id = obj.document_id
        return cls.instance_id


class Measurement(Base):
    __tablename__ = 'fact_measurement'
    measurement_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey('dim_document.document_id'), nullable=False)
    time_s = Column(Numeric, nullable=False, comment='Time since start of data collection in seconds')
    torque_Nm = Column(Numeric, nullable=False, comment='Torque measured from the screwdriver')


class LogLevel(Base):
    ''' Lookup table '''
    __tablename__ = 'dim_log_level'
    level = Column(Integer, primary_key=True, comment='Level priority')
    level_name = Column(String, nullable=False, comment='E.g. ERROR or INFO')


class Log(Base):
    ''' Software log table '''
    __tablename__ = 'fact_log'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey('dim_document.document_id'))
    created_at = Column(DateTime, nullable=False, comment='Log entry date and time')
    logger = Column(String, nullable=False, comment='Name of the logger')
    level = Column(Integer, ForeignKey('dim_log_level.level'), nullable=False)
    trace = Column(String, comment='Error traceback')
    message = Column(String, nullable=False, comment='Log entry')


class EventType(Base):
    ''' Lookup table '''
    __tablename__ = 'dim_event_type'
    event_type = Column(String, primary_key=True, comment='Event type character (e.g., D for distraction)')
    event_type_description = Column(String)


# NOTE: Objects in EVENT_TYPES should not be inserted to the database to prevent side effects from SQLAlchemy's
# lazy loading
# Instead, only copies of EVENT_TYPES object are to be inserted
EVENT_TYPE_DISTRACTION = EventType(event_type='D', event_type_description='Distraction event')
EVENT_TYPES = (EVENT_TYPE_DISTRACTION,)


class AnnotatedEvent(Base):
    __tablename__ = 'fact_annotated_event'
    event_type = Column(String, ForeignKey('dim_event_type.event_type'), primary_key=True, comment='TODO')
    event_num = Column(Integer, primary_key=True, comment='TODO')
    document_id = Column(String, ForeignKey('dim_document.document_id'), primary_key=True)
    event_begin = Column(Numeric, comment='Allow placeholder as NULL')
    event_end = Column(Numeric, comment='Allow placeholder as NULL')


def export_schema_graph(name: str):
    '''
    Export schema graph as a .png image.
    NOTE: Requires Graphviz (download from http://www.graphviz.org/download/)
    '''
    from sqlalchemy_schemadisplay import create_schema_graph
    graph = create_schema_graph(metadata=Base.metadata, show_datatypes=False, show_indexes=False,
                                rankdir='TB', concentrate=False)
    graph.write_png(name)
