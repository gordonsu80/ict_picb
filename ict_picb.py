#-------------------------------------------------------------------------------
# Name:        ict_PICB
# Purpose:     PICB ICT test fixture function test script
#
# Author:      SUGG
#
# Created:     11/08/2024
# Copyright:   (c) SUGG 2024
# Licence:     <your licence>
#
# Version:
#   7.0.0   20Nov   initial release for 90000135-114_C
#   7.0.1   09Jan   fixed the issue where LLS output grounded by relay during
#                   linearity test
#
# To do:
#   to find tune PM_IN and PM_VAC_IN value based on testing result
#
#-------------------------------------------------------------------------------
SCRIPT_VER = 'Script Ver 7.0.1'


import sys
import os
import time
import re
from my_ict import *



MCU_BL_VER      = 'FW:3.5.0'
MCU_FW_VER      = 'FW:5.1.2'
FPGA_VER        = 'FPGA:3.0'
ROTARY_SW       = '0'
BRD_REV_NO      = '2'
BOARD_REVISION  = 'Board Rev {}, Part num 0, Dash num 0'.format(BRD_REV_NO)

MCU_APP_FW_BIN  = 'PICB_1190_101_5_1_2.bin'
FPGA_BIN        = ''
DUMMY_FF_BIN    = '0xFF.bin'
FPGA_DB_VER     = 'FPGA:99.1'

DAC_PER_VOLT12  = 4095.0/3.3
LLS_NOISE_LIMIT = 50


picb0 = {'cmdHandle': None, 'debugHandle': None, 'ipAddr': '192.168.2.64',
        'cmdPort': 50002, 'debugPort': 50001, 'prompt': ''}


picb1 = {'cmdHandle': None, 'debugHandle': None, 'ipAddr': '192.168.2.65',
        'cmdPort': 50002, 'debugPort': 50001, 'prompt': ''}


picb2 = {'cmdHandle': None, 'debugHandle': None, 'ipAddr': '192.168.2.66',
        'cmdPort': 50002, 'debugPort': 50001, 'prompt': ''}


#-------------------------------------------------------------------------------
# Description:
# Parameter:
#
#-------------------------------------------------------------------------------
def PICB_supply_voltage(board):
    f_pass = True

    myLog('Supply voltage analog input test started', 's')

    ch      = [0, 1, 2, 3, 4, 5, 6]
    name    = ['VMON_12V_MINUS', 'VMON_5V', 'VMON_DDS_LO', 'VMON_DDS_HI', 'VMON_12V', 'VMON_3_3V', 'VMON_PM_BIAS']
    volt    = [-12, 5, 1, 1, 12, 3.3, 1]
    scale    = [ (-2.05/10)*DAC_PER_VOLT12,
                1.0/2*DAC_PER_VOLT12,
                DAC_PER_VOLT12,
                DAC_PER_VOLT12,
                1.37/(1.37+5.23)*DAC_PER_VOLT12,
                3.57/(3.57+1.15)*DAC_PER_VOLT12,
                3.0*(1+(23.2+0.133)/10)*102/(102+309)*DAC_PER_VOLT12
                ]

    for i, val in enumerate(ch):
        # see firmware cb_ain.c file line 420. data = ain_int_chan[ain_chnl].raw >> 2;
        adc_val = AIN_read(board, val)*4

        if not (i==2 or i==3):  # VMON_DDS_LO and VMON_DDS_HI no checking
            if adc_val > volt[i]*scale[i]*1.10 or adc_val < volt[i]*scale[i]*0.90:
                f_pass = False
                myLog('CH{} expected: {} measured: {}'.format(i, int(volt[i] * scale[i]), adc_val), 'F')
            else:
                myLog('CH{} expected: {} measured: {}'.format(i, int(volt[i] * scale[i]), adc_val), 's')

        val_meas = adc_val / scale[i]
        myLog('CH ' + name[i] + ' voltage: ' + str(val_meas) + 'V', 's')


    if f_pass:
        myLog('Supply voltage analog input test completed', 'P')
    else:
        myLog('Supply voltage analog input test completed', 'F')

    return f_pass


#-------------------------------------------------------------------------------
# Description:
#   J19.3 (IN+) has 3.3k 1% pull-up
#   J19.4 (IN-) has 3.3k 1% pull-down
#   8R (relay open)  are connected between J19.3 (IN+) and J19.4 (IN-)
#       measured voltage: 10V -> 5.004V -> 4.991V -> GND => 13mV; 0.142V -> 2.814V
#       measured resistance: 3.293k -> 8 -> 3.293k => 12mV
#   4R (relay closed)
#       measured voltage: 10V -> 5.000V -> 4.994V -> GND => 6mV; 0.071V -> 2.16V
#       measured resistance: 3.293k -> 4 -> 3.293k => 6mV
#-------------------------------------------------------------------------------
def PICB_pressue_sensor(board):
    f_pass  = True

    myLog('PM sensor input test started', 's')

    FACTOR_FIXTURE_HW = 0.96    # compensate for actual resistor on fixture

    # with relay open
    pm_r = 0.008 * FACTOR_FIXTURE_HW  # 8 ohm
    eth_cmd_write(board, 'DIOS 768 0')    # LLS output un-grounded
    eth_debug_read(board)
    time.sleep(1)
    if f_pass:
        f_pass, pm_measure1 = p_pressue_sensor(pm_r)

    # with relay close
    pm_r = 0.004 * FACTOR_FIXTURE_HW  # 4 ohm
    eth_cmd_write(board, 'DIOS 768 1')    # LLS output grounded
    eth_debug_read(board)
    time.sleep(1)
    if f_pass:
        f_pass, pm_measure2 = p_pressue_sensor(pm_r)

    # PM reading should be smaller with relay closed
    for i in [0, 1]:
        if pm_measure1[i] < pm_measure2[i]:
            f_pass = False

    eth_cmd_write(board, 'DIOS 768 0')  # LLS output un-grounded

    if f_pass:
        myLog('PM sensor input test finished', 'P')
    else:
        myLog('PM sensor input test finished', 'F')

    return f_pass


def p_pressue_sensor(r_sense):
    pm_bias_volt = 3.0 * ((23.2+0.133)/10.0 + 1.0)
    pm_in_p = pm_bias_volt * (3.3 + r_sense) / (3.3 + r_sense +3.3)
    pm_in_n = pm_bias_volt * (3.3 / (3.3 + r_sense +3.3))
    pm_sensor = pm_in_p - pm_in_n

    gain_u55 = 1.0 + 50.0/4.7
    gain_u56 = 1.0 + 50.0/(6.04+0.0412)
    pm_in = pm_sensor*gain_u55 + 3.0*332.0/(332.0+1000.0) # offset R324 and R330
    pm_vac_in = pm_sensor*gain_u55*gain_u56 + 1.50 # offset by U53

    #          0.864,     2.572          0.748                   1.5
    u61_mux = ['PM_IN',  'PM_VAC_IN',    'A2D_REF3.0V',          '1_5VOLT_BIAS']
    val_typ = [pm_in,     pm_vac_in,     3.0*332/(1000+332),     3.0*2.32/(2.32+2.32)]
    val_min = [pm_in*0.9, pm_vac_in*0.9, 3.0*332/(1000+332)*0.9, 3.0*2.32/(2.32+2.32)*0.9]
    val_max = [pm_in*1.1, pm_vac_in*1.1, 3.0*332/(1000+332)*1.1, 3.0*2.32/(2.32+2.32)*1.1]

    pm_measure = []

    # U61 mux input: PM_VAC_IN
    for idx, val in enumerate(u61_mux):
        eth_cmd_write(board, 'SMUX ' + str(idx)) # select MUX (U61) input
        eth_debug_read(board)

        time.sleep(0.1)
        adc_cnt = r16(board, 0x60006000)
        adc_volt = 3.0 * adc_cnt / pow(2, 16)
        myLog(val+' reading: '+str(adc_cnt)+' (ADC) '+str(adc_volt)+'V', 'd')

        if adc_volt < val_min[idx]:
            myLog(u61_mux[idx]+' expected >'+str(val_min[idx])+' got '+str(adc_volt), 'F')
            f_pass = False
        elif adc_volt > val_max[idx]:
            myLog(u61_mux[idx]+' expected <'+str(val_max[idx])+' got '+str(adc_volt), 'F')
            f_pass = False
        else:
            myLog(u61_mux[idx] + ' expected: ' + str(val_typ[idx]) + ' got ' + str(adc_volt), 's')
            f_pass = True

        if idx==0 or idx==1:
            pm_measure.append(adc_cnt)

    return (f_pass, pm_measure)


#-------------------------------------------------------------------------------
# Description:  toggle one output and check one input
#
# Parameter:
#-------------------------------------------------------------------------------
def PICB_LLS_chX_debug(board, ch=0, lls_freq=100, f_plot=False):
    """
    PICB_LLS_chX_debug(ch=0, lls_freq=100, f_plot=False)
    """
    f_pass  = True

    myLog('LLS CH '+str(ch)+' debug test started', 's')

    eth_cmd_write(board, 'SFREQ '+str(lls_freq))
    eth_cmd_write(board, 'EN '+ str(ch))

    noise_s = ''
    avg_s = ''
    noise_i = []
    avg_i = []
    #----------------------------------------------------
    # test gain linearity
    # input gain
    for gout in range(0, 10):
        print('\n', gout, ' out of 9    ')
        for gin in range(0, 10):
            print(gout*10 + gin)

            gain_in = str(gin*10+9)
            gain_out = str(gout*10 + 9)

            eth_cmd_write(board, 'SGAIN '+gain_in+' '+gain_out)
            time.sleep(0.1)
            eth_cmd_write(board, 'NOISE')
            temp = eth_debug_read(board)

            n = re.findall('LLS Noise \d+ Min', temp)[0][10:-4]
            noise_s = noise_s + n + ', '
            noise_i.append(int(n))

            a = re.findall(' Avg \d+ Max', temp)[0][5:-4]
            avg_s = avg_s + a + ', '
            avg_i.append(int(a))

            temp1 = re.findall('Avg \d* Max', temp)
            if len(temp1) != 1:
                myLog(temp, 'F')
                f_pass = False

    myLog('LLS noise:   ', 's')
    myLog(noise_s, 'v')
    myLog('', 's')

    myLog('LLS average: ', 's')
    myLog(avg_s, 'v')
    myLog('', 's')

    # write average and noise date to .csv file for plotting and analysing
    with open(sys.argv[2] + '_LLS.csv', 'a+') as f:
        f.write('CH'+str(ch)+' LLS_value, '+avg_s+'\n')
        f.write('CH'+str(ch)+' LLS_noise, '+noise_s+'\n')

    if f_plot == True:
        try:
            from matplotlib import pyplot as pl

            pl.subplot(211)
            pl.title('LLS Average ')
            pl.plot(avg_i)
            pl.subplot(212)
            pl.title('noise')
            pl.plot(noise_i)
            pl.suptitle('LLS test - CH\n'+str(ch))
            pl.show()
        except ImportError:
            myLog('Import matplotlib Error', 'F')
            eth_ports_close(board)
            sys.exit("""matplotlib library is missing\n
                        run pip install matplotlib in DOS""")

    if f_pass:
        myLog('LLS CH '+str(ch)+' debug test finished', 'P')
    else:
        myLog('LLS CH '+str(ch)+' debug test finished', 'F')

    return f_pass


#-------------------------------------------------------------------------------
# Description:
#
#-------------------------------------------------------------------------------
def PICB_LLS_test_chX(board, ch=0, lls_freq=100):
    f_pass  = True

    myLog('LLS CH '+str(ch)+' input linearity test started - '+str(lls_freq), 's')

    eth_cmd_write(board, 'DIOS 768 0')  # LLS output un-grounded

    eth_cmd_write(board, 'SFREQ '+str(lls_freq))
    eth_cmd_write(board, 'EN '+ str(ch))
    eth_debug_read(board)

    #----------------------------------------------------
    # test gain linearity - input gain
    for idx_g, gain_out in enumerate([80]):
        avg_i = []
        noise_i = []
        avg_s = ''
        noise_s = ''
        for i in range(0, 10): # 1 ... 9
            gain = i*10 + 9
            # SGAIN <in> <out>  Set Gains
            eth_cmd_write(board, 'SGAIN '+str(gain)+' '+str(gain_out))
            time.sleep(0.1)
            eth_cmd_write(board, 'NOISE')
            temp = eth_debug_read(board)

            if len(re.findall('LLS Noise \d+ Min', temp)) == 1:
                n = re.findall('LLS Noise \d+ Min', temp)[0][10:-4]
                noise_s = noise_s + n + ', '
                noise_i.append(int(n))
            else:
                myLog('LLS Noise value not found', 'F')
                f_pass = False

            if len(re.findall('Avg \d+ Max', temp)) == 1:
                a = re.findall(' Avg \d+ Max', temp)[0][5:-4]
                avg_s = avg_s + a + ', '
                avg_i.append(int(a))
            else:
                myLog('LLS Avg value not found', 'F')
                f_pass = False

        myLog('CH '+str(ch)+', SGAIN X '+str(gain_out)+', LLS_noise,  '+noise_s, 's')
        myLog('CH '+str(ch)+', SGAIN X '+str(gain_out)+', LLS_averag, '+avg_s, 's')

        if avg_i[0] > 1500:
            myLog('avg[0] is out of spec '+str(avg_i[0])+' 1200', 'F')
            f_pass = False

        if avg_i[9] < 3000:
            myLog('avg[0] is out of spec '+str(avg_i[9])+' 3000', 'F')
            f_pass = False

        for idx in range(0, 9):
            # when output not saturates output should increase with increasing input
            if (avg_i[idx+1]<4000) and (avg_i[idx]>avg_i[idx+1]):
                myLog('Output did NOT increase with incresing gain', 'F')
                myLog('step '+str(idx)+' '+str(avg_i[idx])+' '+str(avg_i[idx+1]), 'F')
                f_pass = False

        for idx, item in enumerate(noise_i):
            if item > LLS_NOISE_LIMIT:
                myLog('Noise exceed limit '+ str(item), 'F')
                f_pass = False

    if f_pass:
        myLog('LLS CH '+str(ch)+' test finished', 'P')
    else:
        myLog('LLS CH '+str(ch)+' test finished', 'F')

    return f_pass


#-------------------------------------------------------------------------------
# Description:
#
#-------------------------------------------------------------------------------
def PICB_LLS_test_ch4(board, lls_freq=100):
    """
    PICB_LLS_test_ch4(lls_freq=100)
    """
    f_pass  = True

    myLog('LLS CH 4 test started - '+str(lls_freq), 's')

    eth_cmd_write(board, 'DIOS 768 0')  # LLS output un-grounded

    eth_cmd_write(board, 'EN 4')

    for freq in [90, 120, 105]:
        eth_cmd_write(board, 'SFREQ '+str(freq))
        eth_cmd_write(board, 'GFREQ ')
        eth_debug_read_find(board, 'LLS GET Freq '+str(freq))

    for phase in [0, 180, 270, 99, 47]:
        eth_cmd_write(board, 'SPHASE '+str(freq))
        eth_cmd_write(board, 'GPHASE ')
        eth_debug_read_find(board, 'LLS GET Phase '+str(freq))

    eth_cmd_write(board, 'SFREQ '+str(lls_freq))

    #----------------------------------------------------
    # test gain linearity - output gain
    myLog('Testing LLS gain linearity - output gain', 's')
    avg_i = []
    noise_i = []
    avg_s = ''
    noise_s = ''
    for i in range(0, 10):
        gain = i*10 + 9
        eth_cmd_write(board, 'SGAIN 30 '+str(gain)) # SGAIN <in> <out>
        time.sleep(0.1)
        eth_cmd_write(board, 'NOISE')
        temp = eth_debug_read(board)

        if len(re.findall('LLS Noise \d+ Min', temp)) == 1:
            t = re.findall('LLS Noise \d+ Min', temp)[0][10:-4]
            noise_i.append(int(t))
            noise_s = noise_s + t + ', '
        else:
            myLog('LLS Noise value not found', 'F')
            f_pass = False

        if len(re.findall('Avg \d+ Max', temp)) == 1:
            t = re.findall('Avg \d+ Max', temp)[0][4:-4]
            avg_i.append(int(t))
            avg_s = avg_s + t + ', '
        else:
            myLog('LLS Avg value not found', 'F')
            f_pass = False

    myLog('CH 4, '+'SGAIN 30 X, LLS_noise,   '+noise_s, 's')
    myLog('CH 4, '+'SGAIN 30 X, LLS_average, '+avg_s, 's')

    if avg_i[0] > 1500:
        myLog('avg[0] is out of spec '+str(avg_i[0])+' 1200', 'F')
        f_pass = False

    if avg_i[9] < 3500:
        myLog('avg[0] is out of spec '+str(avg_i[9])+' 3600', 'F')
        f_pass = False

    for idx in range(0, 9):
        # when output not saturates output should increase with increasing input
        if (avg_i[idx+1]<4000) and (avg_i[idx]>avg_i[idx+1]):
            myLog('Output did NOT increase with incresing gain', 'F')
            myLog('step '+str(idx)+' '+str(avg_i[idx])+' '+str(avg_i[idx+1]), 'F')
            f_pass = False

    # check noise value
    for idx, item in enumerate(noise_i):
        if item > LLS_NOISE_LIMIT:
            myLog('Noise exceed limit '+ str(item), 'F')
            f_pass = False

    #----------------------------------------------------
    # LLS output grounded during calibration
    myLog('Testing LLS otuput short to ground', 's')
    eth_cmd_write(board, 'SGAIN 99 99')
    for i in range (0, 3):
        eth_cmd_write(board, 'DIOS 768 1') # LLS output grounded
        time.sleep(1)
        eth_cmd_write(board, 'NOISE')
        temp = eth_debug_read(board)
        if len(re.findall('Avg \d+ Max', temp)) == 1:
            t = re.findall('Avg \d+ Max', temp)[0][4:-4]
            if int(t) > 640:
                myLog('LLS output grounded, expected < 640', 'F')
                f_pass = False
        else:
            myLog('LLS Avg value not found', 'F')
            f_pass = False

        eth_cmd_write(board, 'DIOS 768 0') # LLS output not grounded
        time.sleep(1)
        eth_cmd_write(board, 'NOISE')
        if eth_debug_read_find(board, 'Avg 4095 Max') == []:
            myLog('LLS output not grounded, expected 4095', 'F')
            f_pass = False

    if f_pass:
        myLog('LLS CH 4 test finished', 'P')
    else:
        myLog('LLS CH 4 test finished', 'F')

    return f_pass



#-------------------------------------------------------------------------------
# Description:  toggle one output and check one input
#
# Parameter:
#	GPIO
#       0	Input	J3.3        z_home_in
#
#       1	Input	J13.2       theta_home_in   <-> J8.1/2 PM_CS
#       6	Input	J10.1       teknic_gpo0_in  <-> J8.3/4 PM_SCLK
#       7	Input	J10.2       teknic_gpo1_in  <-> J8.5/6 PM_MOSI
#
#		768	Output	J11.4       crsh_sensor_en_b
#       4	Input	J11.5       crsh_in
#-------------------------------------------------------------------------------
def PICB_GPIO_test(board):
    f_pass  = True

    myLog('GPIO test started', 's')

    myLog('GPIO output 768 and GPIO input 4 test started', 's')
    gpio_out = ['1', '0']
    gpio_in  = ['0', '1']

    for loop in range(0, 10):
        for i, e in enumerate(gpio_out):
            eth_cmd_write(board, 'DIOS 768 ' + e)
            rtn = eth_cmd_write(board, 'DIOG 4')
            eth_debug_read(board)

            temp = re.findall('Bit 4 Value \d', rtn)
            if not (len(temp)==1 and temp[0][-1]==gpio_in[i]):
                f_pass = False
                myLog('DIOS 768 ' + e, 's')
                myLog('DIOG 4 expected ' + gpio_in[i], 'F')

    if f_pass:
        myLog('GPIO output 768 and GPIO input 4 test completed', 'P')


    myLog('Opto-coupler outputs and GPIO input 0 test started', 's')
    # the command below de-activates all Opto-coupler outputs (pulled HIGH)
    eth_cmd_write(board, 'SZL 1 1 1 1 1 1 1 1 1 1')
    eth_cmd_write(board, 'STL 1 1 1 1 1 1 1 1')
    eth_debug_read(board)

    # STL   LLS_POSITIVE            LLS_NEGATIVE
    #       THETA_HOME_POSITIVE     THETA_HOME_NEGATIVE
    #       THETA_GND_POSITIVE      THETA_GND_NEGATIVE
    #       FORCE_LIMIT_POSITIVE    FORCE_LIMIT_NEGATIVE
    # eth_cmd_write(board, 'STL 1 1 1 0 1 1 1 0')  # both '0' assert J10.6
    # eth_cmd_write(board, 'STL 1 1 0 1 1 1 0 1')  # both '0' assert J10.5
    cmds = ['STL 1 1 1 0 1 1 1 0', 'STL 1 1 1 1 1 1 1 1',
            'STL 0 1 0 1 0 1 0 1', 'STL 1 1 1 1 1 1 1 1']
    gpio_in = ['1', '0', '1', '0']


    for loop_no in range(0, 10):
        for i, cmd in enumerate(cmds):
            eth_cmd_write(board, cmd)
            rtn = eth_cmd_write(board, 'DIOG 0')
            eth_debug_read(board)

            temp = re.findall('Bit 0 Value \d', rtn)
            if not (len(temp) == 1 and temp[0][-1] == gpio_in[i]):
                f_pass = False
                myLog(cmd + ' DIOG 0 expected ' + gpio_in[i], 'F')

    # the command below de-activates all Opto-coupler outputs (pulled HIGH)
    eth_cmd_write(board, 'SZL 1 1 1 1 1 1 1 1 1 1')
    eth_cmd_write(board, 'STL 1 1 1 1 1 1 1 1')
    eth_debug_read(board)

    # SZL   LLS_POSITIVE            LLS_NEGATIVE
    #       Z_HOME_POSITIVE         Z_HOME_NEGATIVE
    #       Z_GND_POSITIVE          Z_GND_NEGATIVE
    #       CRASH_POSITIVE          CRASH_NEGATIVE
    #       FORCE_LIMIT_POSITIVE    FORCE_LIMIT_NEGATIVE
    # eth_cmd_write(board, 'SZL 1 1 1 0 1 1 1 1 1 0') # both '0' assert J10.4
    # eth_cmd_write(board, 'SZL 1 1 0 1 1 1 1 1 0 1') # both '0' assert J10.3
    cmds = ['SZL 1 1 1 0 1 1 1 1 1 0', 'SZL 1 1 1 1 1 1 1 1 1 1',
            'SZL 1 1 0 1 1 1 1 1 0 1', 'SZL 1 1 1 1 1 1 1 1 1 1']
    gpio_in = [ '1', '0', '1', '0']

    for loop_no in range(0, 10):
        for i, cmd in enumerate(cmds):
            eth_cmd_write(board, cmd)
            rtn = eth_cmd_write(board, 'DIOG 0')
            eth_debug_read(board)

            temp = re.findall('Bit 0 Value \d', rtn)
            if not (len(temp) == 1 and temp[0][-1] == gpio_in[i]):
                f_pass = False
                myLog(cmd + ' DIOG 0 expected ' + gpio_in[i], 'F')

    if f_pass:
        myLog('Opto-coupler outputs and GPIO input 0 test completed', 'P')

    myLog('testing RS485 outputs and GPIO input 1/6/7', 's')
    gpio_in = ['1', '6', '7']
    for i, e in enumerate(gpio_in):
        for j in range(0, 5):  # check for 10 toggles
            for k in range (0, 25):
                rtn = eth_cmd_write(board, 'DIOG ' + e)
                eth_debug_read(board)

                if re.findall('Bit ' + e + ' Value 1', rtn) != []:
                    #myLog('toggling HIGH seen at GPIO ' + e + ' ' + str(k), 's')
                    break
                if k == 99:
                    f_pass = False
                    myLog('toggling HIGH NOT seen at GPIO ' + e, 'F')

            for k in range (0, 25):
                rtn = eth_cmd_write(board, 'DIOG ' + e)
                eth_debug_read(board)

                if re.findall('Bit ' + e + ' Value 0', rtn) != []:
                    #myLog('toggling LOW seen at GPIO ' + e + ' ' + str(k), 's')
                    break
                if k == 99:
                    f_pass = False
                    myLog('toggling LOW NOT seen at GPIO ' + e, 'F')

    if f_pass:
        myLog('GPIO test finished', 'P')
    else:
        myLog('GPIO test finished', 'F')

    return f_pass



#-------------------------------------------------------------------------------
# Description:
# Parameter:
#
#-------------------------------------------------------------------------------
def PICB_test_sequence(board):
    status = True
    f_skip_check = True

    print('starting test sequence')

    if status or f_skip_check:
        status = PICB_supply_voltage(board)

    if status or f_skip_check:
        status = PICB_GPIO_test(board)

    if status or f_skip_check:
        status = PICB_pressue_sensor(board)

    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 0, 100)  # J14 loopback CH0 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 0, 105)
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 1, 100)  # J15 loopback CH1 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 1, 105)
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 2, 100)  # J16 loopback CH2 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 2, 105)
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 3, 100)  # J17 loopback CH3 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 3, 105)

    if status or f_skip_check:
        status = PICB_LLS_test_ch4(board, 100)  # on-board loopback CH4 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_ch4(board, 105)

    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 5, 100)  # J18 loopback CH5 of U66
    if status or f_skip_check:
        status = PICB_LLS_test_chX(board, 5, 105)
    
    return status


#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
def main_p1(board):
    status = True

    myLog('\n' + myTime(2), 'h')
    myLog('===============================================================================', 'h')
    myLog(SCRIPT_VER, 's')
    myLog(sys.argv[0]+' '+sys.argv[1]+' '+sys.argv[2]+' '+sys.argv[3], 's')

    if not eth_ports_open(board):
        sys.exit()

    if status:
        status = cmd_debug_verify(board, 'VER', 'Ver ' + MCU_FW_VER + ' ' + FPGA_VER)

    if status:
        # BDID returns rotary switch position in TOCB app FW
        # BDID returns 0 in TOCB bootloader
        status = cmd_debug_verify(board, 'BDID', 'Board ID ' + ROTARY_SW)
    if status:
        status = cmd_debug_verify(board, 'BDT', 'IA')
    if status:
        status = check_board_revision(board, BOARD_REVISION)
    if status:
        status = cmd_debug_verify(board, 'MCUID', 'MCU ID 0x451, Rev 0x1001, SERNUM')
    if status:
        status = cmd_debug_verify(board, 'DGC', '0, 0, 0, 0, 0, 0, 0 No Faults #0')

    if status:
        status = eth_cmd_write(board, 'RBL')
        time.sleep(10)

    if status:
        myLog('part 1 done - PASS', 'P')
    else:
        myLog('part 1 done - FAIL', 'F')



#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
def main_p2(board):
    status = True

    myLog(sys.argv[0]+' '+sys.argv[1]+' '+sys.argv[2]+' '+sys.argv[3], 's')

    if not eth_ports_open(board):
        sys.exit()

    if status:
        status = cmd_debug_verify(board, 'VER', 'Ver ' + MCU_BL_VER + ' ' + FPGA_VER)

    if status:
        eth_ports_close(board)

    if status:
        status = programming_MCU_exe(board, MCU_APP_FW_BIN)

    if status:
        time.sleep(10)  # wait for board boot up to application firmware

    if status:
        myLog('part 2 done - PASS', 'P')
    else:
        myLog('part 2 done - FAIL', 'F')



#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
def main_p3(board):
    status = True

    myLog(sys.argv[0]+' '+sys.argv[1]+' '+sys.argv[2]+' '+sys.argv[3], 's')

    if not eth_ports_open(board):
        sys.exit()

    if status:
        status = cmd_debug_verify(board, 'VER', 'Ver ' + MCU_FW_VER + ' ' + FPGA_VER)

    if status:
        status = POST(board, [])

    if status:
        status = PICB_test_sequence(board)

    if status:
        status = POST(board, [])

    eth_ports_close(board)

    if status:
        myLog('part 3 done - PASS', 'P')
    else:
        myLog('part 3 done - FAIL', 'F')



#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
def main_p4(board):
    status = True

    myLog(sys.argv[0]+' '+sys.argv[1]+' '+sys.argv[2]+' '+sys.argv[3], 's')

    if not eth_ports_open(board):
        sys.exit()

    if status:
        status = cmd_debug_verify(board, 'VER', 'Ver ' + MCU_FW_VER + ' ' + FPGA_VER)

    if status:
        # BDID returns rotary switch position in TOCB app FW
        # BDID returns 0 in TOCB bootloader
        status = cmd_debug_verify(board, 'BDID', 'Board ID ' + ROTARY_SW)
    if status:
        status = cmd_debug_verify(board, 'BDT', 'IA')
    if status:
        status = check_board_revision(board, BOARD_REVISION)
    if status:
        status = cmd_debug_verify(board, 'MCUID', 'MCU ID 0x451, Rev 0x1001, SERNUM')
    if status:
        status = cmd_debug_verify(board, 'DGC', '0, 0, 0, 0, 0, 0, 0 No Faults #0')

    eth_ports_close(board)

    if status:
        myLog('part 4 done - PASS', 'P')
    else:
        myLog('part 4 done - FAIL', 'F')

    pass



#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
def main_p999(board):
    status = True

    myLog(sys.argv[0]+' '+sys.argv[1]+' '+sys.argv[2]+' '+sys.argv[3], 's')

    FACTOR_FIXTURE_HW = 0.96
    r_sense = 0.004*FACTOR_FIXTURE_HW

    for r_sense in [0.004*FACTOR_FIXTURE_HW, 0.008*FACTOR_FIXTURE_HW]:
        pm_bias_volt = 3.0 * ((23.2+0.133)/10.0 + 1.0)
        pm_in_p = pm_bias_volt * (3.3 + r_sense) / (3.3 + r_sense +3.3)
        pm_in_n = pm_bias_volt * (3.3 / (3.3 + r_sense +3.3))
        pm_sensor = pm_in_p - pm_in_n

        gain_u55 = 1.0 + 50.0/4.7
        gain_u56 = 1.0 + 50.0/(6.04+0.0412)
        pm_in = pm_sensor*gain_u55 + 3.0*332.0/(332.0+1000.0) # offset R324 and R330
        pm_vac_in = pm_sensor*gain_u55*gain_u56 + 1.50 # offset by U53

        if r_sense == 0.008*FACTOR_FIXTURE_HW:
            print('pm_in expected:     ' + str(pm_in) + '  measured/expected:   ' + str(100-0.885269165*100/pm_in) + "%")
        elif r_sense == 0.004*FACTOR_FIXTURE_HW:
            print('pm_in expected:     ' + str(pm_in) + '  measured/expected:   ' + str(100-0.813766479*100/pm_in) + "%")


    pass


#-------------------------------------------------------------------------------
# Description:
# Parameter:
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    status = True
    os.chdir('log')

    if len(sys.argv) != 4:
        print('Invalid command - missing parameter')
        print('format: ict_picb.py <ip_address> <log_file_name> <test_item>')
        print('\n\nExiting ...')
        time.sleep(5)
        sys.exit()

    if sys.argv[1] != picb0['ipAddr']:
        print('format: ict_picb.py <ip_address> <log_file_name> <test_item>')
        print('Wrong IP address')
        print('\n\nExiting ...')
        time.sleep(5)
        sys.exit()

    board = picb0

    if sys.argv[3] == '1':      # switching to bootloader
        main_p1(board)
    elif sys.argv[3] == '2':    # downloadng App firmware
        main_p2(board)
    elif sys.argv[3] == '3':
        main_p3(board)
    elif sys.argv[3] == '4':
        main_p4(board)
        ict_result_parse(sys.argv[2] + '_log.txt')
    elif sys.argv[3] == '999':
        main_p999(board)

    pass



