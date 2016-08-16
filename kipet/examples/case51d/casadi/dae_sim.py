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
from kipet.sim.CasadiSimulator import *
#from kipet.sim.Simulator import interpolate_from_trayectory
from kipet.utils.data_tools import *
import matplotlib.pyplot as plt
import numpy as np
import sys

import pickle

def rxn_rates(df,fix_traj,params):

    times = sorted(df.index)
    names = ['r0','r1','r2','r3']#,'rc','rd']
    r = list()
    r.append(lambda t: params['k1']*df['SA'][t]*df['AA'][t])
    r.append(lambda t: params['k2']*df['ASA'][t]*df['AA'][t])
    r.append(lambda t: params['k3']*df['ASAA'][t]*df['H2O'][t])
    r.append(lambda t: params['k4']*df['AA'][t]*df['H2O'][t])

    """
    C_sat = lambda t: 0.000403961838576*(fix_traj['T'][t]-273.15)**2 - 0.002335673472454*(fix_traj['T'][t]-273.15)+0.428791235875747    
    C_asa = lambda t: df['ASA'][t]
    rc = lambda t: 0.3950206559*params['kc']*(C_asa(t)-C_sat(t)+((C_asa(t)-C_sat(t))**2+1e-6)**0.5)**1.34
    r.append(rc)
    """
    r_data = pd.DataFrame(index=times)

    for i,n in enumerate(names):
        values = list()
        for t in times:
            values.append(r[i](t))
        r_data[n] = values
    return r_data


if __name__ == "__main__":
    

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
    params['k1'] = 0.0360309
    params['k2'] = 0.1596062
    params['k3'] = 6.8032345
    params['k4'] = 1.8028763
    params['kc'] = 0.7566864
    params['kd'] = 7.1108682
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
    gammas['SA']=    [-1, 0, 0, 0, 0, 1]
    gammas['AA']=    [-1,-1, 0,-1, 0, 0]
    gammas['ASA']=   [ 1,-1, 1, 0,-1, 0]
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
        r.append(m.Y[t,'r0']-m.P['k1']*m.Z[t,'SA']*m.Z[t,'AA'])
        r.append(m.Y[t,'r1']-m.P['k2']*m.Z[t,'ASA']*m.Z[t,'AA'])
        r.append(m.Y[t,'r2']-m.P['k3']*m.Z[t,'ASAA']*m.Z[t,'H2O'])
        r.append(m.Y[t,'r3']-m.P['k4']*m.Z[t,'AA']*m.Z[t,'H2O'])

        # cristalization rate
        C_sat = m.Y[t,'Csat']
        C_asa = m.Z[t,'ASA']
        #rc = 0.3950206559*m.P['kc']*(C_asa-C_sat+((C_asa-C_sat)**2+1e-6)**0.5)**1.34
        rc = ca.if_else((C_asa-C_sat)>0.0,
                        m.P['kc']*(fabs(C_asa-C_sat))**1.34,
                        0.0)
        #print rc
        r.append(m.Y[t,'r4']-rc)
        # disolution rate
        C_sat = m.P['Csa']
        C_sa = m.Z[t,'SA']
        m_sa = m.X[t,'Msa']
        #step = 0.5*(1+m_sa/(m_sa**2+1e-2**2)**0.5)
        step = 1.0/(1.0+ca.exp(-m_sa/1e-7))
        rd = m.P['kd']*(C_sat-C_sa)**1.90*step
        #rd = 0.0 #ca.if_else(m_sa>=0.0,
                 #m.P['kd']*(C_sat-C_sa)**1.90,
                 #0.0)
        r.append(m.Y[t,'r5']-rd)

        Cin = 39.1
        v_sum = 0.0
        V = m.X[t,'V']
        f = m.Y[t,'f']
        for c in m.mixture_components:
            v_sum += partial_vol[c]*(sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in xrange(6))+ epsilon[c]*f/V*Cin)
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
            vol_sum += partial_vol[c]*(sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in xrange(6))+ epsilon[c]*f/V*Cin)
        exprs['V'] = V*m.Y[t,'v_sum']

        # mass balances
        for c in m.mixture_components:
            exprs[c] = sum(gammas[c][j]*m.Y[t,'r{}'.format(j)] for j in xrange(6))+ epsilon[c]*f/V*Cin - m.Y[t,'v_sum']*m.Z[t,c]

        exprs['Masa'] = 180.157*V*m.Y[t,'r4']
        exprs['Msa'] = -138.121*V*m.Y[t,'r5']
        return exprs

    builder.set_odes_rule(rule_odes)
    
    #casadi_model = builder.create_casadi_model(0.0,210.5257)    
    casadi_model = builder.create_casadi_model(0.0,210.5257)    

    casadi_model.pprint()
    
    sim = CasadiSimulator(casadi_model)
    # defines the discrete points wanted in the concentration profile
    sim.apply_discretization('integrator',nfe=400)
    # simulate

    sim.fix_from_trajectory('Y','Csat',fixed_traj)
    sim.fix_from_trajectory('Y','f',fixed_traj)
    results_casadi = sim.run_sim("idas")
    
    # display concentration results

    with open('init2.pkl', 'wb') as f:
        pickle.dump(results_casadi, f)
    
    results_casadi.Z.plot.line(legend=True)
    plt.xlabel("time (s)")
    plt.ylabel("Concentration (mol/L)")
    plt.title("Concentration Profile")

    C.plot()
    
    plt.figure()
    
    results_casadi.Y['Csat'].plot.line()
    plt.plot(fixed_traj['Csat'],'*')
    plt.xlabel("time (s)")
    plt.ylabel("Csat")
    plt.title("Saturatuon Concentration")
    
    plt.figure()
    
    results_casadi.X['V'].plot.line()
    plt.plot(fixed_traj['V'],'*')
    plt.xlabel("time (s)")
    plt.ylabel("volumne (L)")
    plt.title("Volume Profile")


    plt.figure()
    
    results_casadi.X['Msa'].plot.line()
    plt.plot(fixed_traj['Msa'],'*')
    plt.xlabel("time (s)")
    plt.ylabel("m_dot (g)")
    plt.title("Msa Profile")
    

    plt.figure()
    results_casadi.Y['f'].plot.line()
    plt.xlabel("time (s)")
    plt.ylabel("flow (K)")
    plt.title("Inlet flow Profile")

    plt.show()
    sys.exit()
    
    plt.figure()
    
    results_casadi.X['Masa'].plot.line()
    plt.plot(fixed_traj['Masa'],'*')
    plt.xlabel("time (s)")
    plt.ylabel("m_dot (g)")
    plt.title("Masa Profile")
    
    plt.show()
    

