#  _________________________________________________________________________
#
#  Kipet: Kinetic parameter estimation toolkit
#  Copyright (c) 2016 Eli Lilly.
#  _________________________________________________________________________

# Sample Problem 2 (From Sawall et.al.)
# First example from WF paper simulation of ODE system using pyomo discretization and IPOPT
#
#		\frac{dZ_a}{dt} = -k_1*Z_a	                Z_a(0) = 1
#		\frac{dZ_b}{dt} = k_1*Z_a - k_2*Z_b		Z_b(0) = 0
#               \frac{dZ_c}{dt} = k_2*Z_b	                Z_c(0) = 0

from kipet.model.TemplateBuilder import *
from kipet.sim.PyomoSimulator import *
from kipet.utils.data_tools import *
import matplotlib.pyplot as plt
import numpy as np
import sys



if __name__ == "__main__":
    
    with_plots = True
    if len(sys.argv)==2:
        if int(sys.argv[1]):
            with_plots = False
    

    fixed_traj = read_absorption_data_from_txt('extra_states.txt')
    C = read_absorption_data_from_txt('concentrations.txt')
    
    # create template model 
    builder = TemplateBuilder()    

    # components
    components = dict()
    components['SA'] = 1.0714                  # Salicitilc acid
    components['AA'] = 9.3828               # Acetic anhydride
    components['ASA'] = 0.0177                 # Acetylsalicylic acid
    components['HA'] = 0.0177                  # Acetic acid
    components['ASAA'] = 0.000015                # Acetylsalicylic anhydride
    components['H2O'] = 0.0                 # water

    builder.add_mixture_component(components)

    # add parameters
    params = dict()
    params['k0'] = 0.0360309
    params['k1'] = 0.1596062
    params['k2'] = 6.8032345
    params['k3'] = 1.8028763
    params['kd'] = 7.1108682
    params['kc'] = 0.7566864
    params['Csa'] = 2.06269996

    builder.add_parameter(params)

    # add additional state variables
    extra_states = dict()
    extra_states['V'] = 0.0202
    extra_states['Masa'] = 0.0
    extra_states['Msa'] = 9.537
    
    builder.add_complementary_state_variable(extra_states)

    algebraics = ['f','r0','r1','r2','r3','r4','r5','v_sum','Csat']
    builder.add_algebraic_variable(algebraics)

    gammas = dict()
    gammas['SA']=    [-1, 0, 0, 0, 1, 0]
    gammas['AA']=    [-1,-1, 0,-1, 0, 0]
    gammas['ASA']=   [ 1,-1, 1, 0, 0,-1]
    gammas['HA']=    [ 1, 1, 1, 2, 0, 0]
    gammas['ASAA']=  [ 0, 1,-1, 0, 0, 0]
    gammas['H2O']=   [ 0, 0,-1,-1, 0, 0]


    epsilon = dict()
    epsilon['SA']= 0.0
    epsilon['AA']= 0.0
    epsilon['ASA']= 0.0
    epsilon['HA']= 0.0
    epsilon['ASAA']= 0.0
    epsilon['H2O']= 1.0
    
    partial_vol = dict()
    partial_vol['SA']=0.0952552311614
    partial_vol['AA']=0.101672206869
    partial_vol['ASA']=0.132335206093
    partial_vol['HA']=0.060320218688
    partial_vol['ASAA']=0.186550717015
    partial_vol['H2O']=0.0883603912169
    
    def rule_algebraics(m,t):
        r = list()
        r.append(m.Y[t,'r0']-m.P['k0']*m.Z[t,'SA']*m.Z[t,'AA'])
        r.append(m.Y[t,'r1']-m.P['k1']*m.Z[t,'ASA']*m.Z[t,'AA'])
        r.append(m.Y[t,'r2']-m.P['k2']*m.Z[t,'ASAA']*m.Z[t,'H2O'])
        r.append(m.Y[t,'r3']-m.P['k3']*m.Z[t,'AA']*m.Z[t,'H2O'])

        # disolution rate
        step = 1.0/(1.0+exp(-m.X[t,'Msa']/1e-4))
        rd = m.P['kd']*(m.P['Csa']-m.Z[t,'SA']+1e-6)**1.90*step
        r.append(m.Y[t,'r4']-rd)
        #r.append(m.Y[t,'r4'])
        
        # cristalization rate
        diff = m.Z[t,'ASA'] - m.Y[t,'Csat']
        rc = 0.3950206559*m.P['kc']*(diff+((diff)**2+1e-6)**0.5)**1.34
        r.append(m.Y[t,'r5']-rc)

        Cin = 26.1
        v_sum = 0.0
        V = m.X[t,'V']
        f = m.Y[t,'f']
        for c in m.mixture_components:
            v_sum += partial_vol[c]*(sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in range(6))+ epsilon[c]*f/V*Cin)
        r.append(m.Y[t,'v_sum']-v_sum)

        return r

    builder.set_algebraics_rule(rule_algebraics)
    
    def rule_odes(m,t):
        exprs = dict()

        V = m.X[t,'V']
        f = m.Y[t,'f']
        Cin = 41.4
        # volume balance
        vol_sum = 0.0
        for c in m.mixture_components:
            vol_sum += partial_vol[c]*(sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in range(6))+ epsilon[c]*f/V*Cin)
        exprs['V'] = V*m.Y[t,'v_sum']

        # mass balances
        for c in m.mixture_components:
            exprs[c] = sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in range(6))+ epsilon[c]*f/V*Cin - m.Y[t,'v_sum']*m.Z[t,c]

        exprs['Masa'] = 180.157*V*m.Y[t,'r5']
        exprs['Msa'] = -138.121*V*m.Y[t,'r4']
        return exprs

    builder.set_odes_rule(rule_odes)

    meas_times = [float(t) for t in range(0,210,10)]
    builder.add_measurement_times(meas_times)
    S_frame = read_absorption_data_from_csv('Slk.csv')
    builder.add_absorption_data(S_frame)
    model = builder.create_pyomo_model(0.0,210.5257)    
    
    sim = PyomoSimulator(model)
    # defines the discrete points wanted in the concentration profile
    sim.apply_discretization('dae.collocation',nfe=100,ncp=1,scheme='LAGRANGE-RADAU')
    
    # good initialization
    initialization = pd.read_csv("init_Z.csv",index_col=0)
    sim.initialize_from_trajectory('Z',initialization)
    sim.scale_variables_from_trajectory('Z',initialization)
    initialization = pd.read_csv("init_X.csv",index_col=0)
    sim.initialize_from_trajectory('X',initialization)
    sim.scale_variables_from_trajectory('X',initialization)
    initialization = pd.read_csv("init_Y.csv",index_col=0)
    sim.initialize_from_trajectory('Y',initialization)
    sim.scale_variables_from_trajectory('Y',initialization)

    sim.fix_from_trajectory('Y','Csat',fixed_traj)
    sim.fix_from_trajectory('Y','f',fixed_traj)

    options = {'halt_on_ampl_error' :'yes'}
    options['nlp_scaling_method'] = 'user-scaling'
    results = sim.run_sim('ipopt',
                          tee=True,
                          solver_opts=options)
    if with_plots:
        # display concentration results    
        results.Z.plot.line(legend=True)
        plt.xlabel("time (s)")
        plt.ylabel("Concentration (mol/L)")
        plt.title("Concentration Profile")

        results.S.plot.line(legend=True)
        plt.xlabel("wave length (s)")
        plt.ylabel("Absorbance")
        plt.title("Absorbance Profile")

        C.plot()
        
        plt.figure()
        
        results.Y['Csat'].plot.line()
        plt.plot(fixed_traj['Csat'],'*')
        plt.xlabel("time (s)")
        plt.ylabel("Csat")
        plt.title("Saturatuon Concentration")
        
        plt.figure()
        
        results.X['V'].plot.line()
        plt.plot(fixed_traj['V'],'*')
        plt.xlabel("time (s)")
        plt.ylabel("volumne (L)")
        plt.title("Volume Profile")


        plt.figure()
        
        results.X['Msa'].plot.line()
        plt.plot(fixed_traj['Msa'],'*')
        plt.xlabel("time (s)")
        plt.ylabel("m_dot (g)")
        plt.title("Msa Profile")
        

        plt.figure()
        results.Y['f'].plot.line()
        plt.xlabel("time (s)")
        plt.ylabel("flow (K)")
        plt.title("Inlet flow Profile")

        plt.figure()
        results.X['Masa'].plot.line()
        plt.plot(fixed_traj['Masa'],'*')
        plt.xlabel("time (s)")
        plt.ylabel("m_dot (g)")
        plt.title("Masa Profile")

        results.D.T.plot(legend=False)
        plot_spectral_data(results.D,dimension='3D')
        results.D.to_csv("Dtl.csv")

        
        plt.show()
    
