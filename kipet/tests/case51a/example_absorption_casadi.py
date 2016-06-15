#  _________________________________________________________________________
#
#  Kipet: Kinetic parameter estimation toolkit
#  Copyright (c) 2016 Eli Lilly.
#  _________________________________________________________________________

# Sample Problem 2 (From Sawall et.al.)
# Basic simulation of ODE with spectral data using multistep-integrator 
#
#		\frac{dZ_a}{dt} = -k*Z_a	Z_a(0) = 1
#		\frac{dZ_b}{dt} = k*Z_a		Z_b(0) = 0
#
#               C_k(t_i) = Z_k(t_i) + w_k(t_i)    for all t_i in measurement points
#               D_{i,j} = \sum_{k=0}^{Nc}C_k(t_i)S_k(l_j) + \xi_{i,j} for all t_i, for all l_j 


from kipet.model.TemplateBuilder import *
from kipet.sim.CasadiSimulator import *
from kipet.utils.data_tools import *
import matplotlib.pyplot as plt
import os
import sys

if __name__ == "__main__":

    # read 100x3 S matrix
    # this defines the measurement lambdas l_j but the t_i still need to be passed
    filename = 'data_sets{}Slk_case51.txt'.format(os.sep)
    S_frame = read_absorption_data_from_txt(filename)

    # create template model 
    builder = TemplateBuilder()    
    builder.add_mixture_component('A',1)
    builder.add_mixture_component('B',0)
    builder.add_mixture_component('C',0)
    builder.add_parameter('k1',2.0)
    builder.add_parameter('k2',0.2)
    # includes absorption data in the template and defines measurement sets
    builder.add_absorption_data(S_frame)
    builder.add_measurement_times([i*0.0333 for i in range(300)])

    # define explicit system of ODEs
    def rule_odes(m,t):
        exprs = dict()
        exprs['A'] = -m.P['k1']*m.C[t,'A']
        exprs['B'] = m.P['k1']*m.C[t,'A']-m.P['k2']*m.C[t,'B']
        exprs['C'] = m.P['k2']*m.C[t,'B']
        return exprs

    builder.set_rule_ode_expressions_dict(rule_odes)
    
    # create an instance of a casadi model template
    # the template includes
    #   - C variables indexed over time and components names e.g. m.C[t,'A']
    #   - C_noise variables indexed over measurement t_i and components names e.g. m.C_noise[t_i,'A']
    #   - P parameters indexed over the parameter names m.P['k']
    #   - D spectra data indexed over the t_i, l_j measurement points m.D[t_i,l_j]
    casadi_model = builder.create_casadi_model(0.0,10.0)

    # create instance of simulator
    sim = CasadiSimulator(casadi_model)
    # defines the discrete points wanted in the profiles (does not include measurement points)
    sim.apply_discretization('integrator',nfe=500)
    # simulate
    results_casadi = sim.run_sim("cvodes")

    # displary concentrations and absorbances results
    plt.figure()
    plt.xlabel("time (s)")
    plt.ylabel("Concentration (mol/L)")
    plt.title("Concentration Profile")
    plt.plot(results_casadi.C_noise)

    # take a look at the data
    plot_spectral_data(results_casadi.D,dimension='3D')
    plt.figure()
    # basic principal component analysis of the data
    basic_pca(results_casadi.D,n=4)
    plt.show()

    
    #write_spectral_data_to_csv('Dij_basic.csv',D_frame)
    #red = read_spectral_data_from_csv('Dij_basic.csv')

    #write_spectral_data_to_txt('Dij_basic.txt',D_frame)
    #red2 = read_spectral_data_from_txt('Dij_basic.txt')
    
