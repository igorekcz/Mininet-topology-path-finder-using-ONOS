# Mininet-topology-path-finder-using-ONOS
Made for "Sieci i chmury teleinformatyczne" course at WUT

exampleTopo.py and topo.json define a network topology. We can use exampleTopo.py as a custom topo in mininet.
When mininet is running and is connected to ONOS we can send requests to the ONOS Rest API to give switches optimal paths using djikstra's algorithm based on data provided in topo.json.