"""
- power_on
- power_off
- start
- stop
- set_axis
- homing
- power_status
- mount_sample
- unmount_sample
- (status)
- (calibrate_sam)
- (compare_sam)
"""
import os
import socket

from pathlib import Path

import pytest
from mock import call, Mock, patch

from emaapi import (mount_sample, power_off, power_on, reset, restart, start,
                    stop, Robot, unmount_sample)


# These tests are just to ensure the correct mapping between function and
# message sent
@patch('emaapi.ema')
def test_power_off(ema_mock):
    power_off()
    assert ema_mock.mock_calls == [call.send('powerOff')]


@patch('emaapi.ema')
def test_power_on(ema_mock):
    power_on()
    assert ema_mock.mock_calls == [call.send('powerOn')]


@patch('emaapi.ema')
def test_reset(ema_mock):
    reset()
    assert ema_mock.mock_calls == [call.send('reset')]


@patch('emaapi.ema')
def test_restart(ema_mock):
    restart()
    assert ema_mock.mock_calls == [call.send('restartMotor')]


@patch('emaapi.ema')
def test_start(ema_mock):
    start()
    assert ema_mock.mock_calls == [call.send('start')]


@patch('emaapi.ema')
def test_stop(ema_mock):
    stop()
    assert ema_mock.mock_calls == [call.send('stopMotor')]


# Methods inside the implementation of the robot class
@patch('socket.socket')
def test_init(mock_sock):
    ema = Robot()
    assert ema.sample_index is None
    assert ema.x_coord is None
    assert ema.y_coord is None
    assert ema.homed is False
    assert ema.connected is False
    assert ema.address is None
    assert ema.port is None
    assert ema.config_file == os.path.join(Path.home(), '.robot.ini')
    assert mock_sock.mock_calls == [call(socket.AF_INET, socket.SOCK_STREAM)]


@patch('configparser.ConfigParser')
def test_set_homed(conf_mock):
    with patch('emaapi.Robot.send') as send_mock:
        ema = Robot(None)
        assert ema.homed is False
        ema.set_homed()
        assert ema.homed is True
        send_calls = [call('gate', wait_for='moveGate:done'),
                      call('homing', wait_for='homing:done')
                      ]
        send_mock.assert_has_calls(send_calls)


@patch('configparser.ConfigParser')
def test_set_sample_coords(conf_mock):
    with patch('emaapi.Robot.send') as send_mock:
        ema = Robot()
        ema.set_sample_coords(75)
        send_mock.assert_called_with('setAxis#X8#Y5', wait_for='setAxis:done')


def test_read_config():
    ema = Robot(config_file='./example_config.ini')
    ema.__read_config__()
    assert ema.address == '127.0.0.2'
    assert ema.port == 10005


@patch('configparser.ConfigParser')
@patch('socket.socket')
def test_connect(sock_mock, conf_mock):
    ema = Robot()
    ema.address = '127.0.0.3'
    ema.port = 10006
    assert ema.connected is False
    ema.connect()
    assert ema.connected is True
    ema.disconnect()
    assert ema.connected is False
    ema.connect()
    assert ema.connected is True
    sock_calls = [call(socket.AF_INET, socket.SOCK_STREAM),
                  call().connect(('127.0.0.3', 10006)),
                  call().close(),
                  call().connect(('127.0.0.3', 10006))]
    assert sock_mock.mock_calls == sock_calls


# Method supports set_sample_coords
def test_sample_to_coords():
    assert (2, 2) == Robot.samplenr_to_xy(12)
    assert (6, 3) == Robot.samplenr_to_xy(53)
    assert (22, 7) == Robot.samplenr_to_xy(217)
    assert (1, 2) == Robot.samplenr_to_xy(2)

    with pytest.raises(ValueError, match=r".*greater than 0"):
        Robot.samplenr_to_xy(0)


# The following tests are for functions which wait for a message to return from
# the robot before continuing
@patch('emaapi.ema')
def test_mount_sample(ema_mock):
    samcoords_mock = Mock()
    homed_mock = Mock()
    send_mock = Mock()
    ema_mock.set_sample_coords = samcoords_mock
    ema_mock.homed = False
    ema_mock.set_homed = homed_mock
    ema_mock.send = send_mock

    mount_sample(75)
    # Preparation for mounting...
    samcoords_mock.assert_called_with(75)
    homed_mock.assert_called_once()
    # ... and the actual process:
    send_calls = [call('next', wait_for='moveNext:done'),
                  call('pick', wait_for='pickSample:done'),
                  call('gate', wait_for='moveGate:done'),
                  call('spinner', wait_for='moveSpinner:done'),
                  call('release', wait_for='releaseSample:done'),
                  call('offside', wait_for='moveOffside:done')
                  ]
    send_mock.assert_has_calls(send_calls)


@patch('emaapi.ema')
def test_unmount_sample(ema_mock):
    unmount_sample()
    send_calls = [call.send('spinner', wait_for='moveSpinner:done'),
                  call.send('pick', wait_for='pickSample:done'),
                  call.send('gate', wait_for='moveGate:done'),
                  call.send('current', wait_for='returnCurrent:done'),
                  call.send('release', wait_for='releaseSample:done')
                  ]
    ema_mock.assert_has_calls(send_calls)
