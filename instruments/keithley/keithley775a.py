#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Driver for the Keithley 775A programmable counter/timer
"""

# IMPORTS #####################################################################


import time
import struct
from enum import Enum, IntEnum

import instruments.units as u

from instruments.abstract_instruments import Instrument
from instruments.util_fns import ProxyList

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
        dump = 3      # 140 readings per second, BCD format

    class SRQ_mask(IntEnum):
        """
        Enum containign SRQ mask settings
        """
        disabled = 0
        on_overflow = 1
        on_self_test_done = 2
        on_reading_done = 8
        on_ready = 16
        on_error = 32

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
        Enum containing data control XXX
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
        Class representing a channel on the Keithley 775A counter/timer.
        """

        def __init__(self, parent, idx):
            assert idx == 0 or idx == 1
            self._parent = parent
            self._idx = idx+1  # one based
            self._ch = ('A' if idx == 0 else 'B')

        # PROPERTIES #

        @property
        def coupling(self):
            raise NotImplementedError

        @coupling.setter
        def coupling(self, newval):
            if not isinstance(newval, Keithley775A.Coupling):
                raise TypeError("Coupling must be of Keithley775A.Coupling type")
            self._parent.sendcmd('{}C{}X'.format(self._ch, newval.value))

        @property
        def attenuator(self):
            raise NotImplementedError

        @attenuator.setter
        def attenuator(self, newval):
            if not isinstance(newval, Keithley775A.Attenuator):
                raise TypeError("Attenuator must be of Keithley775A.Attenuator type")
            self._parent.sendcmd('{}A{}X'.format(self._ch, newval.value))

        @property
        def filter(self):
            raise NotImplementedError

        @filter.setter
        def filter(self, newval):
            if not isinstance(newval, bool):
                raise TypeError("Filter must be of bool type")
            self._parent.sendcmd('{}F{}X'.format(self._ch, ('1' if newval else '0')))

        @property
        def slope(self):
            raise NotImplementedError

        @slope.setter
        def slope(self, newval):
            if not isinstance(newval, Keithley775A.Slope):
                raise TypeError("Attenuator must be of Keithley775A.Slope type")
            self._parent.sendcmd('{}S{}X'.format(self._ch, newval.value))

        @property
        def trigger(self):
            raise NotImplementedError

        @trigger.setter
        def trigger(self, newval):
            """
            Type: float or voltage
            Note: changing the trigger level will also change the attentuator setting.
            """
            if not isfloat(newval):
                raise TypeError("Trigger must be of a number")
            cmd = '{}L{:+07.2f}X'.format(self._ch, newval)
            self._parent.sendcmd(cmd)

    # PROPERTIES #

    @property
    def channel(self):
        """
        Gets a specific channel object.

        For example, the following would set the coupling of channel 1:

        >>>> counter = ik.keithley.Keithley775A.open_gpibusb("/dev/ttyUSB0", 10)
        >>>> counter.channel[0].coupling = ik.keithley.Keithley775A.Coupling.DC

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
        return self.parse_status_word(self.get_status_word())['mode']

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
        raise NotImplementedError

    @rate.setter
    def rate(self, newval):
        if not isinstance(newval, Keithley775A.Rate):
            raise TypeError("Rate must be of Keithley775A.Rate type")
        self.sendcmd('S{}X'.format(newval.value))

    @property
    def gate_time(self):
        raise NotImplementedError

    @gate_time.setter
    def gate_time(self, newval):
        """
        Get/set gate time for the Keithley 775A. Power-on default is 1s.

        :type: `~quantities.quantity.Quantity`
        """
        if isinstance(newval, str):
            if (newval == "U"):
                self.sendcmd("GUX");
                return
        if not isconvertible(newval, 's'):
            raise TypeError("Gate time must be convertible to seconds")
        gt = newval.rescale('s')
        cmd = 'G{:f}X'.format(gt[()]) # quantity objects are numpy arrays
        self.sendcmd(cmd)

    @property
    def delay_time(self):
        raise NotImplementedError

    @delay_time.setter
    def delay_time(self, newval):
        """
        Get/set delay time for the Keithley 775A. Power-on default is 1s.

        :type: `~quantities.quantity.Quantity`
        """
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
        raise NotImplementedError

    @delay.setter
    def delay(self, newval):
        if not isinstance(newval, bool):
            raise TypeError("Delay must be of bool type")
        self.sendcmd('I{}X'.format('1' if newval else '0'))

    @property
    def displayed_digits(self):
        raise NotImplementedError

    @displayed_digits.setter
    def displayed_digits(self, newval):
        if not isinstance(newval, int):
            raise TypeError("Delay must be of int type")
        if not(newval >= 3 and newval <=9):
            raise RuntimeError("Display digits n=3 to 9")
        self.sendcmd('N{}X'.format(newval))

    def trigger(self):
        """
        One-shot in S0 mode
        """
        self.sendcmd('TX')

    @property
    def EOI(self):
        raise NotImplementedError

    @EOI.setter
    def EOI(self, newval):
        if not isinstance(newval, bool):
            raise TypeError("Delay must be of bool type")
        self.sendcmd('K{}X'.format('1' if newval else '0'))

    @property
    def SRQ_mask(self):
        raise NotImplementedError

    @SRQ_mask.setter
    def SRQ_mask(self, newval):
        if not isinstance(newval, int):
            raise TypeError("Delay must be of int type")
        if not(newval >= 0 and newval <=59):
            raise RuntimeError("SRQ mask out of range")
        self.sendcmd('M{}X'.format(newval))

    @property
    def terminator(self):
        raise NotImplementedError

    @terminator.setter
    def terminator(self, newval):
        if not isinstance(newval, Keithley775A.Terminator):
            raise TypeError("Rate must be of Keithley775A.Terminator type")
        self.sendcmd('Y{}X'.format(newval.value))

    @property
    def display_mode(self):
        raise NotImplementedError

    @display_mode.setter
    def display_mode(self, newval):
        if not isinstance(newval, Keithley775A.DisplayMode):
            raise TypeError("Rate must be of Keithley775A.DisplayMode type")
        self.sendcmd('D{}X'.format(newval.value))

    def show_message(self, msg):
        self.sendcmd('D5{}X'.format(msg))

    @property
    def data_format(self):
        raise NotImplementedError

    @data_format.setter
    def data_format(self, newval):
        if not isinstance(newval, Keithley775A.DataFormat):
            raise TypeError("Rate must be of Keithley775A.DataFormat type")
        self.sendcmd('P{}X'.format(newval.value))

    @property
    def totalize(self):
        raise NotImplementedError

    @totalize.setter
    def totalize(self, newval):
        if not isinstance(newval, Keithley775A.Totalize):
            raise TypeError("Rate must be of Keithley775A.Totalize type")
        self.sendcmd('TO{}X'.format(newval.value))

    def self_test(self):
        """
        Perform self-test.
        """
        self.sendcmd('JX')

    @property
    def data_control(self):
        raise NotImplementedError

    @data_control.setter
    def data_control(self, newval):
        if not isinstance(newval, Keithley775A.DataControl):
            raise TypeError("Rate must be of Keithley775A.DataControl type")
        self.sendcmd('B{}X'.format(newval.value))

    def get_measuring_buffer(self):
        self.data_control = Keithley775A.DataControl.measuring_buffer
        return self.query("") # as string

    def get_gate_time(self):
        self.data_control = Keithley775A.DataControl.gate_time
        result = self.query("") # TODO: USER
        return float(result) # as floating point

    def get_delay_time(self):
        self.data_control = Keithley775A.DataControl.delay_time
        result = self.query("")
        return float(result) # as floating point

    def get_trigger_level_A(self):
        self.data_control = Keithley775A.DataControl.trigger_level_A
        result = self.query("")
        return float(result) # as floating point

    def get_trigger_level_B(self):
        self.data_control = Keithley775A.DataControl.trigger_level_B
        result = self.query("")
        return float(result) # as floating point

    def read(self, trigger = False):
        """
        Read a value. For one-shot measurements (S0 mode) set trigger=True.
        """
        if trigger:
            self.trigger()
        return self.query("")

    def measure_float(self, trigger = False):
        """
        Read a measurement (converted to float).
        """
        return float(self.read(trigger)) * self.unit

    def measure_int(self, trigger = False):
        """
        Read a measurement (converted to int).
        """
        return float(self.read(trigger))

    def reset(self):
        """
        Set the instrument in the default conditions
        """
        self.sendcmd('F0AC0AA0AF0AS0BC0BA0BF0BS0I0D0P0N9K0M00S1Y0G0W0AL0BL0TO0X')
        self.unit = u.Hz

    def get_status_word(self, U):
        self.sendcmd('U{}X'.format(U))
        return self.query("")

    def get_operating_mode(self):
        return self.get_status_word(U=0)

    def get_error_status(self):
        return self.get_status_word(U=1)

    def __init__(self, filelike):
        """
        The constructor sets the instrument to the default settings, except
        for terminator (no terminator setting) and data format (without prefix
        with leading zeros).
        """
        super(Keithley775A, self).__init__(filelike)
        self.reset()
        self.terminator  = Keithley775A.Terminator.no_terminator
        self.data_format = Keithley775A.DataFormat.without_prefix_with_leading_zero

