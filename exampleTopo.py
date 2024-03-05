from mininet.topo import Topo
import math

class MyTopo(Topo):
    def __init__(self):
        super(MyTopo, self).__init__()
        
        # Creating 10 switches, one for each of the 10 cities
        cities = ["BER", "PAR", "WAW", "GDN", "AMS", "MAD", "FRF", "STO", "VNN", "ROM"]
        switches = []
        hosts = []
        for i, city in enumerate(cities):
            switch = self.addSwitch(f's{i+1}')
            switches.append(switch)
            host = self.addHost(city)
            hosts.append(host)
            self.addLink(hosts[i], switches[i], delay='0.1ms')

        # Creating links between the city switches
        self.addLink(switches[0], switches[1], bw=15, delay='6.21ms') # Berlin - Paris
        self.addLink(switches[0], switches[2], bw=15, delay='3.66ms') # Berlin - Warsaw
        self.addLink(switches[0], switches[6], bw=10, delay='3ms') # Berlin - Frankfurt
        self.addLink(switches[0], switches[8], bw=15, delay='3.7ms') # Berlin - Vienna
        self.addLink(switches[0], switches[7], bw=10, delay='5.73ms') # Berlin - Stockholm
        self.addLink(switches[1], switches[4], bw=10, delay='3.04ms') # Paris - Amsterdam
        self.addLink(switches[1], switches[5], bw=10, delay='7.44ms') # Paris - Madrid
        self.addLink(switches[2], switches[3], bw=10, delay='2ms') # Warsaw - Gdansk
        self.addLink(switches[8], switches[9], bw=10, delay='5.41ms') # Vienna - Rome
		# New links for lab2
        self.addLink(switches[1], switches[6], bw=10, delay='3.37ms') # Paris - Frankfurt
        self.addLink(switches[6], switches[8], bw=10, delay='4.24ms') # Frankfurt - Vienna
        self.addLink(switches[8], switches[2], bw=10, delay='3.93ms') # Vienna - Warsaw
		

topos = { 'euTopo': ( lambda: MyTopo() ) }