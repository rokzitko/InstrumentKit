#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Driver for the Keithley 775A programmable counter/timer

Rok Zitko, March 2020
"""

# https://pyvisa.readthedocs.io/en/latest/api/resources.html#pyvisa.resources.GPIBInstrument
# https://pyvisa.readthedocs.io/en/latest/api/visalibrarybase.html

# IMPORTS #####################################################################

import time
from enum import Enum, IntEnum

import instruments.units as u

from instruments.abstract_instruments import Instrument
from instruments.util_fns import ProxyList
from instruments.abstract_instruments.comm import VisaCommunicator
from pyvisa import constants

# CLASSES #####################################################################

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def isconvertible(value, unit):
    try:
        x = value.rescale(unit)
        return True
    except ValueError:
        return False

class Keithley775A(Instrument):


    """
    The Keithley 775A is a 120Mhz counter/timer. You can
    find the full specifications in the `Keithley 775A manual`_.

    Example usage:

    >>> import instruments as ik
    >>> counter = ik.keithley.Keithley775A.open_gpibusb('/dev/ttyUSB0', 12)
    >>> print counter.measure(counter.Mode.frequency_A)

    .. _Keithley 775A manual: https://www.tek.com/manual/keithley-model-775a-programmable-counter-timer-instruction-manual
    """



    # ENUMS #

    class Mode(IntEnum):
        """
        Enum containing valid measurement modes for the Keithley 775A
        """
        frequency_A = 0
        frequency_B = 1
        period_A = 2              # single period measurement
        period_average_A = 3      # number of periods averaged is gate_time/period
        time_interval_A_to_B = 4  # A starts, B stops
        pulse_A = 5               # pulse width
        frequency_C = 6           # if optional module installed
        totalize_A = 7            # cumulative or A gated by B

    class Coupling(IntEnum):
        """
        Enum containing DC/AC coupling settings
        """
        DC = 0
        AC = 1

    class Attenuator(IntEnum):
        """
        Enum containing attenuation settings
        """
        X1 = 0
        X10 = 1

    class Slope(IntEnum):
        """
        Enum containing trigger slope settings
        """
        positive = 0
        negative = 1

    class Rate(IntEnum):
        """
        Enum containing rate settings
        """
        one_shot = 0  # one-shot on T, GET or external timing
        normal = 1    # 3 readings per second (this is the power-on default)
        fast = 2      # 25 readings per second
        dump = 3      # 140 readings per second, BCD format (TODO)

    class SRQ_mask(IntEnum):
        """
        Enum containign SRQ mask settings. Upon power-up, or after a DCL or SDC command,
        SQR is disabled.
        """
        disabled = 0        
        on_overflow = 1        # overflow condition occured
        on_self_test_done = 2  # self test has been completed
        on_reading_done = 8    # reading has been completed
        on_ready = 16          # ready to receive device-dependent commands
        on_error = 32          # error condition occured

    class Terminator(IntEnum):
        """
        Enum containing terminator settings
        """
        CRLF = 0
        LFCR = 1
        CR = 2
        LF = 3
        no_terminator = 4

    class DisplayMode(IntEnum):
        """
        Enum containing display modes
        """
        measurement = 0
        gate_time = 1
        delay_time = 2
        trigger_levels = 3
        totalize_gate = 4
        message = 5

    class DataFormat(IntEnum):
        """
        Enum containing data modes
        """
        with_prefix_without_leading_zero = 0
        without_prefix_without_leading_zero = 1
        with_prefix_with_leading_zero = 2
        without_prefix_with_leading_zero = 3

    class Totalize(IntEnum):
        """
        Enum containing totalize mode (relevant if mode=totalize_A)
        """
        A_by_B = 0      # gating signal on ch B permits counting of ch A pulses
        cumulative = 1  # pulses counted as long as they are present at the input

    class DataControl(IntEnum):
        """
        Enum containing data control (for reading back the current parameters)
        """
        measuring_buffer = 0
        gate_time = 1
        delay_time = 2
        trigger_level_A = 3
        trigger_level_B = 4

    class StatusWord(IntEnum):
        """
        Enum containing the status word
        """
        operating_mode_status = 0
        error_status = 1

    # INNER CLASSES #
    class Channel(Instrument):
        """
        Class representing a channel A or B on the Keithley 775A counter/timer. 
        Channel C does not have any configurable settings.
        """

        def __init__(self, parent, idx):
            assert idx == 0 or idx == 1
            self._parent = parent
            self._idx = idx+1  # one based
            self._ch = ('A' if idx == 0 else 'B')

        # PROPERTIES #

        @property
        def coupling(self):
            """
            Gets/sets the coupling mode for a channel

            :type: `~Keithley775A.Coupling`
            """
            return self._parent.parse_operating_mode()['coupling_{}'.format(self._ch)]
    
        @coupling.setter
        def coupling(self, newval):
            if not isinstance(newval, Keithley775A.Coupling):
                raise TypeError("Coupling must be of Keithley775A.Coupling type")
            self._parent.sendcmd('{}C{}X'.format(self._ch, newval.value))

        @property
        def attenuator(self):
            """
            Gets/sets the attentuator setting for a channel

            :type: `~Keithley775A.Attentuator`
            """
            return self._parent.parse_operating_mode()['attenuator_{}'.format(self._ch)]

        @attenuator.setter
        def attenuator(self, newval):
            if not isinstance(newval, Keithley775A.Attenuator):
                raise TypeError("Attenuator must be of Keithley775A.Attenuator type")
            self._parent.sendcmd('{}A{}X'.format(self._ch, newval.value))

        @property
        def filter(self):
            """
            Gets/sets the filter setting for a channel

            :type: `~Keithley775A.Filter`
            """
            return self._parent.parse_operating_mode()['filter_{}'.format(self._ch)]

        @filter.setter
        def filter(self, newval):
            if not isinstance(newval, bool):
                raise TypeError("Filter must be of bool type")
            self._parent.sendcmd('{}F{}X'.format(self._ch, ('1' if newval else '0')))

        @property
        def slope(self):
            """
            Gets/sets the trigger slope setting for a channel

            :type: `~Keithley775A.Slope`
            """
            return self._parent.parse_operating_mode()['slope_{}'.format(self._ch)]

        @slope.setter
        def slope(self, newval):
            if not isinstance(newval, Keithley775A.Slope):
                raise TypeError("Attenuator must be of Keithley775A.Slope type")
            self._parent.sendcmd('{}S{}X'.format(self._ch, newval.value))

        @property
        def trigger(self):
            """
            Gets/sets the trigger level for a channel

            Note: changing the trigger level will also change the attentuator setting.

            :type: `float` or `~quantities.quantity.Quantity`
            """
            if self._ch == 'A':
                return self._parent.get_trigger_level_A()
            if self._ch == 'B':
                return self._parent.get_trigger_level_B()

        @trigger.setter
        def trigger(self, newval):
            if isinstance(newval, u.quantity.Quantity):
                newval = float(newval)
            if not isfloat(newval):
                raise TypeError("Trigger must be of a float or a unitful quantity")
            cmd = '{}L{:+07.2f}X'.format(self._ch, newval)
            self._parent.sendcmd(cmd)

    # PROPERTIES #

    @property
    def channel(self):
        """
        Gets a specific channel object.

        For example, the following would set the coupling of channel 1:

        >>>> counter = ik.keithley.Keithley775A.open_gpibusb("/dev/ttyUSB0", 10)
        >>>> counter.channel[0].coupling = counter.Coupling.DC

        :rtype: `Keithley775A.Channel`
        """
        return ProxyList(self, Keithley775A.Channel, range(2))

    @property
    def mode(self):
        """
        Gets/sets the measurement mode for the Keithley 775A.

        Example use:

        >>> import instruments as ik
        >>> counter = ik.keithley.Keithley775A.open_gpibusb('/dev/ttyUSB0', 12)
        >>> counter.mode = counter.Mode.frequency_B

        :type: `Keithley775A.Mode`
        """
        return self.parse_operating_mode()['mode']

    @mode.setter
    def mode(self, newval):
        if isinstance(newval, str):
            newval = self.Mode[newval]
        if not isinstance(newval, Keithley775A.Mode):
            raise TypeError("Mode must be specified as a Keithley775A.Mode "
                            "value, got {} instead.".format(newval))
        if newval in [Keithley775A.Mode.frequency_A, Keithley775A.Mode.frequency_B, Keithley775A.Mode.frequency_C]:
            self.unit = u.Hz
        if newval in [Keithley775A.Mode.period_A, Keithley775A.Mode.period_average_A, Keithley775A.Mode.time_interval_A_to_B]:
            self.unit = u.s
        if newval in [Keithley775A.Mode.pulse_A, Keithley775A.Mode.totalize_A]:
            self.unit = 1
        self.sendcmd('F{}X'.format(newval.value))

    @property
    def rate(self):
        """
        Gets/sets the rate setting.

        :type: `Keithley775A.Rate`
        """
        return self.parse_operating_mode()['rate']

    @rate.setter
    def rate(self, newval):
        if not isinstance(newval, Keithley775A.Rate):
            raise TypeError("Rate must be of Keithley775A.Rate type")
        self.sendcmd('S{}X'.format(newval.value))

    @property
    def _data_control(self):
        return self.dc # not queried, but stored in the object

    @_data_control.setter
    def _data_control(self, newval):
        """
        Sets the data control (what value the instrument returns when queried).

        :type: `Keithley775A.DataControl`
        :rtype: `str`
        """
        if not isinstance(newval, Keithley775A.DataControl):
            raise TypeError("Data control must be of Keithley775A.DataControl type")
        if not self.dc is newval:
            self.sendcmd('B{}X'.format(newval.value))
        self.dc = newval

    def get_measuring_buffer(self):
        self._data_control = Keithley775A.DataControl.measuring_buffer # B0 mode
        return self.query("") # as string

    def get_gate_time(self):
        """
        Gets gate time

        :rtype: `~quantities.quantity.Quantity`
        """
        self._data_control = Keithley775A.DataControl.gate_time
        result = self.query("") # note: case of 'USER' not supported
        return float(result) * u.s

    def get_delay_time(self):
        """
        Gets delay time

        :rtype: `~quantities.quantity.Quantity`
        """
        self._data_control = Keithley775A.DataControl.delay_time
        result = self.query("")
        return float(result) * u.s

    def get_trigger_level_A(self):
        """
        Gets trigger level for channel A

        :rtype: `~quantities.quantity.Quantity`
        """
        self._data_control = Keithley775A.DataControl.trigger_level_A
        result = self.query("")
        return float(result) * u.V

    def get_trigger_level_B(self):
        """
        Gets trigger level for channel B

        :rtype: `~quantities.quantity.Quantity`
        """
        self._data_control = Keithley775A.DataControl.trigger_level_B
        result = self.query("")
        return float(result) * u.V

    @property
    def gate_time(self):
        """
        Gets/sets gate time for the Keithley 775A. Power-on default is 1s.

        :type: `~quantities.quantity.Quantity`
        """
        return self.get_gate_time()

    @gate_time.setter
    def gate_time(self, newval):
        if isinstance(newval, str):
            if (newval == "U"): # USER
                self.sendcmd("GUX");
                return
        if not isconvertible(newval, 's'):
            raise TypeError("Gate time must be convertible to seconds")
        gt = newval.rescale('s')
        cmd = 'G{:f}X'.format(gt[()]) # quantity objects are numpy arrays
        self.sendcmd(cmd)

    @property
    def delay_time(self):
        """
        Gets/sets delay time for the Keithley 775A. Power-on default is 1s.

        :type: `~quantities.quantity.Quantity`
        """
        return self.get_delay_time()

    @delay_time.setter
    def delay_time(self, newval):
        if isinstance(newval, str):
            if (newval == "U"):
                self.sendcmd("DUX");
                return
        if not isconvertible(newval, 's'):
            raise TypeError("Gate time must be convertible to seconds")
        dl = newval.rescale('s')
        cmd = 'D{:f}X'.format(dl[()]) # quantity objects are numpy arrays
        self.sendcmd(cmd)

    @property
    def delay(self):
        """
        Gets/sets delay mode

        :type: `bool`
        """
        return self.parse_operating_mode()['delay']

    @delay.setter
    def delay(self, newval):
        if not isinstance(newval, bool):
            raise TypeError("Delay must be of bool type")
        self.sendcmd('I{}X'.format('1' if newval else '0'))

    @property
    def displayed_digits(self):
        """
        Gets/sets the number of digits displayed

        :type: `int`
        """
        return self.parse_operating_mode()['displayed_digits']

    @displayed_digits.setter
    def displayed_digits(self, newval):
        if not isinstance(newval, int):
            raise TypeError("Delay must be of int type")
        if not(newval >= 3 and newval <=9):
            raise RuntimeError("Display digits n=3 to 9")
        self.sendcmd('N{}X'.format(newval))

    def isGPIB(self):
        """
        Returns True if the comminicator is VisaCommunicator
        """
        return isinstance(self._file, VisaCommunicator)

    def assertGPIB(self):
        """
        Asserts that we are communicating via the GPIB bus
        """
        if not self.isGPIB():
            raise RuntimeError("VisaCommunicator required")

    def get_status_byte(self):
        # https://stackoverflow.com/questions/14563634/python-visa-serial-polling-function
        sb = self._file._conn.stb
        return sb

    def sb_rqs(self):
        """
        Did one of the conditions for service request occur?
        Cleared by reading the status byte.
        """
        return self.get_status_byte() & 64

    def sb_error(self):
        """
        Illegal commend received or gate error occured in last measurement cycle?
        Cleared by reading the error status word (U1).
        """
        return self.get_status_byte() & 32

    def sb_ready(self):
        """
        Set after power-up. Cleared when execute command received. Reset after command completed.
        """
        return self.get_status_byte() & 16

    def sb_reading_done(self):
        """
        Set after completion of a measurement cycle. Clear by addressing to talk in the B0 mode.
        """
        return self.get_status_byte() & 8

    def sb_self_test_done(self):
        """
        Set after power-up self test completion of after executing the self test command.
        Clear by reading the error status word (U1).
        """
        return self.get_status_byte() & 2

    def sb_overflow(self):
        """
        Time interval overflow. 
        """
        return self.get_status_byte() & 1

    def trigger(self, wait_SRQ = False):
        """
        Trigger one-shot measurement in the one-shot (S0) mode

        :param mode: If 'cmd', sends the 'T' command. If 'GPIB', uses GPIB trigger.
        :param wait_SRQ: If True, will wait for the completion of the measurement. on_reading_done must be enabled in SRQ mask.
        """
        if self.trigger_mode == 'cmd':
            self.sendcmd('TX')
        elif self.trigger_mode == 'GPIB':
            self.assertGPIB()
            self._file._conn.assert_trigger()
        else:
            raise RuntimeError("Unknown trigger mode {}".format(self.trigger_mode))
        if wait_SRQ:
            while True:
                self._file._conn.wait_for_srq()
                if self.sb_reading_done():
                      break

    @property
    def EOI(self):
        """
        Gets/sets EOI. Default is False.

        :type: `bool`
        """
        return self.parse_operating_mode()['EOI']

    @EOI.setter
    def EOI(self, newval):
        if not isinstance(newval, bool):
            raise TypeError("Delay must be of bool type")
        self.sendcmd('K{}X'.format('1' if newval else '0'))

    @property
    def srq_mask(self):
        """
        Gets/sets the SRQ mask. The input is an integer, which may be constructured
        using the bits from IntEnum SRQ.

        :type: `int`
        """
        return self.parse_operating_mode()['SRQ_mask']

    @srq_mask.setter
    def srq_mask(self, newval):
        if not isinstance(newval, int):
            raise TypeError("SRQ mask must be of int type")
        if not(newval >= 0 and newval <= 59):
            raise RuntimeError("SRQ mask out of range")
        self.sendcmd('M{}X'.format(newval))

    @property
    def terminator(self):
        """
        Gets/sets the terminator string

        :type: `Keithley775A.Terminator`
        """
        return self.parse_operating_mode()['terminator']

    @terminator.setter
    def terminator(self, newval):
        if not isinstance(newval, Keithley775A.Terminator):
            raise TypeError("Rate must be of Keithley775A.Terminator type")
        self.sendcmd('Y{}X'.format(newval.value))

    @property
    def display_mode(self):
        """
        Gets/sets the display mode

        :type: `Keithley775A.DisplayMode
        """
        return self.parse_operating_mode()['display_mode']

    @display_mode.setter
    def display_mode(self, newval):
        if not isinstance(newval, Keithley775A.DisplayMode):
            raise TypeError("Rate must be of Keithley775A.DisplayMode type")
        self.sendcmd('D{}X'.format(newval.value))

    def show_message(self, msg):
        """
        Shows a message on the instrument display

        :type: `str`
        """
        self.sendcmd('D5{}X'.format(msg))

    @property
    def data_format(self):
        """
        Gets/sets the data format of measurements returned through the GPIB bus (prefix, leading zeros).

        :type: `Keithley775A.DataFormat`
        """
        return self.parse_operating_mode()['data_format']

    @data_format.setter
    def data_format(self, newval):
        if not isinstance(newval, Keithley775A.DataFormat):
            raise TypeError("Rate must be of Keithley775A.DataFormat type")
        self.sendcmd('P{}X'.format(newval.value))

    @property
    def totalize(self):
        """
        Gets/sets the totalize mode (cumulative or gated)

        :type: `Keithley775A.Totalize`
        """
        return self.parse_operating_mode()['totalize']

    @totalize.setter
    def totalize(self, newval):
        if not isinstance(newval, Keithley775A.Totalize):
            raise TypeError("Rate must be of Keithley775A.Totalize type")
        self.sendcmd('TO{}X'.format(newval.value))

    def self_test(self):
        """
        Perform the self-test.
        """
        self.sendcmd('JX')

    def read(self, trigger = False):
        """
        Read a value. For one-shot measurements (S0 mode) set trigger=True.

        :param trigger: Trigger a measurement
        :type trigger: `bool`
        :rtype: `str`
        """
        self._data_control = self.DataControl.measuring_buffer
        if trigger:
            self.trigger()
        return self.query("")

    def measure_float(self, trigger = False):
        """
        Read a measurement.

        :param trigger: Trigger a measurement
        :type trigger: `bool`
        :rtype: `float`
        """
        return float(self.read(trigger))

    def measure_int(self, trigger = False):
        """
        Read a measurement.

        :param trigger: Trigger a measurement
        :type trigger: `bool`
        :rtype: `int`
        """
        return int(self.read(trigger))

    def measure(self, trigger = False):
        """
        Read a measurement.

        :param trigger: Trigger a measurement
        :type trigger: `bool`
        :rtype: `int` or `~quantities.quantity.Quantity`
        """
        if self.unit is 1:
            return self.measure_int(trigger)
        return self.measure_float(trigger) * self.unit

    def reset(self):
        """
        Set the instrument in the default conditions
        """
        if self.reset_mode == 'cmd':
            self.sendcmd('F0AC0AA0AF0AS0BC0BA0BF0BS0I0D0P0N9K0M00S1Y0G0W0AL0BL0TO0X')
        elif self.reset_mode == 'GPIB':
            self.assertGPIB()
            # https://pyvisa.readthedocs.io/en/1.5-docs/instruments.html
            self._file._conn.clear() # selective device clear (SDC)
        else:
            raise RuntimeError("Unknown mode {}".format(self.reset_mode))
        self.unit = u.Hz
        self.dc = self.DataControl.measuring_buffer

    def get_status_word(self, U):
        """
        Gets the status word (operating mode or error status)

        :rtype: `str`
        """
        self.sendcmd('U{}X'.format(U))
        return self.query("")

    def get_operating_mode(self):
        """
        Gets the operating mode

        :rtype: `str`
        """
        return self.get_status_word(U=0)

    def get_error_status(self):
        """
        Gets the error status

        :rtype: `str`
        """
        return self.get_status_word(U=1)

    def parse_operating_mode(self):
        """
        Parses the operating mode string

        :rtype: `dict`
        """
        s = self.get_operating_mode()
        assert(s[0:3] == '775')
        result = { "mode": Keithley775A.Mode(int(s[3])), # F
                 "coupling_A": Keithley775A.Coupling(int(s[4])), # AC
                 "attenuator_A": Keithley775A.Attenuator(int(s[5])), # AA
                 "filter_A":  s[6] == '1', # AF
                 "slope_A": Keithley775A.Slope(int(s[7])), # AS
                 "coupling_B": Keithley775A.Coupling(int(s[8])), # BC
                 "attenuator_B": Keithley775A.Attenuator(int(s[9])), # BA
                 "filter_B":  s[10] == '1', # BF
                 "slope_B": Keithley775A.Slope(int(s[11])), # BS 
                 "delay": s[12] == '1', # I
                 "display_mode": Keithley775A.DisplayMode(int(s[13])), # D
                 "data_format": Keithley775A.DataFormat(int(s[14])), # P
                 "displayed_digits": int(s[15]), # N
                 "EOI": s[16] == '1', # K
                 "SRQ_mask": int(s[17:][:2]), # M
                 "rate": Keithley775A.Rate(int(s[19])), # S
                 "terminator": Keithley775A.Terminator(int(s[20])), # Y
                 "totalize": Keithley775A.Totalize(int(s[21])),  # TO
                 }
        return result

    def parse_error_status(self):
        """
        Parses the error status string

        :rtype: `dict`
        """
        s = self.get_error_status()
        assert(s[0:3] == '775')
        assert(s[-5:] == '00000')
        result = { "IDDC": s[3] == '1', # illegal device-dependent command
                   "IDDCO": s[4] == '1', # illegal device-dependent option
                   "gate_error": s[5] == '1',
                   "self_test_error": s[6] == '1',
                   }
        return result

    def __init__(self, filelike):
        """
        The constructor sets the instrument to the default settings, except
        for terminator (no terminator setting) and data format (without prefix
        with leading zeros).
        """
        super(Keithley775A, self).__init__(filelike)
        self.reset_mode = 'GPIB'
        self.reset()
        self.trigger_mode = 'GPIB'
        self.terminator  = Keithley775A.Terminator.no_terminator
        self.data_format = Keithley775A.DataFormat.without_prefix_with_leading_zero

