import pytest
from cranio.database import session_scope, Session
from cranio.app.widget import SessionWidget


@pytest.fixture
def session_widget(database_fixture):
    # Two sessions in the database: one initialized by database_fixture and other initialized here
    with session_scope() as s:
        s.add(Session())
    session_widget = SessionWidget()
    yield session_widget


def test_session_widget_contains_all_sessions_from_the_database(session_widget):
    assert session_widget.session_count() == 2
    assert len(session_widget.sessions) == 2


def test_session_widget_select_and_click_ok_changes_active_session(session_widget):
    with session_scope() as s:
        session = s.query(Session).filter(Session.session_id != Session.get_instance().session_id).first()
    session_widget.select_session(session_id=session.session_id)
    assert session_widget.active_session_id() == session.session_id

