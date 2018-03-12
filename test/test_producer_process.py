'''
Test module description

Copyright (C) 2017  Simo Tumelius

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
import pytest
import random
import time
import multiprocessing as mp
from daqstore.store import DataStore
from cranio.core import Packet
from cranio.producer import ChannelInfo, Sensor, Producer, ProducerProcess

@pytest.fixture
def store():
    DataStore.queue_cls = mp.Queue
    store = DataStore(buffer_length=10, resampling_frequency=None)
    yield store
    store.cache.delete()
    
def random_value_generator():
    return random.gauss(0, 1)
        
def test_channel_info():
    c = ChannelInfo('torque', 'Nm')
    assert str(c) == 'torque (Nm)'
            
def test_sensor():
    s = Sensor()
    assert s.self_test()
    assert s.read() == None
    ch = ChannelInfo('torque', 'Nm')
    s.add_channel(ch)
    packet = s.read()
    df = packet.as_dataframe()
    assert not df.empty
    assert list(df.columns) == [str(ch)]
            
def test_producer_add_and_remove_sensors():
    n = 3
    p = Producer()
    sensors = [Sensor() for _ in range(n)]
    for s in sensors:
        p.add_sensor(s)
    assert len(p.sensors) == n
    for s in sensors:
        p.remove_sensor(s)
    assert len(p.sensors) == 0
                
def test_producer_process_start_and_join(store):
    p = ProducerProcess('test_process', store)
    p.start()
    assert p.is_alive()
    time.sleep(1)
    assert p.is_alive()
    p.pause()
    assert p.is_alive()
    p.start()
    assert p.is_alive()
    p.pause()
    # read and flush store
    store.read()
    store.flush()
    # no sensors -> empty data
    df = p.read(include_cache=True)
    assert df.empty
    p.join()
    assert not p.is_alive()
    
def test_producer_process_with_sensors(store):
    p = ProducerProcess('test_process', store)
    s = Sensor()
    s._default_value_generator = random_value_generator
    channels = [ChannelInfo('torque', 'Nm'), ChannelInfo('load', 'N'), ChannelInfo('extension', 'mm')]
    for c in channels:
        s.add_channel(c)
    p.producer.add_sensor(s)
    p.start()
    assert p.is_alive()
    time.sleep(1)
    p.pause()
    # read and flush store
    store.read()
    store.flush()
    df = p.read(include_cache=True)
    for c in channels:
        assert str(c) in df
    p.join()
    assert not p.is_alive()