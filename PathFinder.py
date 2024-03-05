import networkx as nx
import networkx.exception
import json
import requests
import msvcrt # Works for Windows OS only
import sys
import os

def topoImport(path):
    """Function for importing topology data from prepared .json file."""
    with open(path, 'r') as data:
        TopoData = json.load(data)
    return TopoData

topoData = topoImport("topo.json")
switches = []
edge_set = set()
flowList = []

for switch in topoData["switches"]:
    switches.append(switch['name'])
    for neighbor in switch['neighbors']:
        link = (switch['name'], topoData['switches'][neighbor['key']]['name'], neighbor['delay'], neighbor['bw'])
        if((link[1], link[0], link[2], link[3]) not in edge_set):
            edge_set.add(link)

S = switches
E = edge_set
F = flowList

with open('template.json', 'r') as f:
    template_json = json.load(f)
    template = json.dumps(template_json, indent=2)

class Flow:
    """Flow class used for creating flow objects, storing their paths, flowDict for storing all flowIds used for sending a DELETE request and keeping track of the allocatedBw."""
    def __init__(self, path: list):
        self.path = path
        self.flowDict = {}
        self.allocatedBw = 0
    
    def deleteFlow(self):
        """Method for using the flowIds stored in flowDict to send DELETE requests to ONOS to remove the entire path."""
        for flow in self.flowDict['flows']:
            url = "http://mininet:8181/onos/v1/flows/" + flow['deviceId'] + "/" + flow['flowId']
            response = requests.delete(url, auth=('karaf', 'karaf'))
            print(response)
        addAvailableBw(self.path, self.allocatedBw)

    def setFlowDict(self, dict):
        self.flowDict = dict

    def setAllocatedBw(self, bw):
        self.allocatedBw = bw

    def checkIfDuplicate(self, h1, h2):
        """Method for checking whether the user is requesting a flow which already exists."""
        return ((h1 == self.path[0] and h2 == self.path[-1]) or (h2 == self.path[0] and h1 == self.path[-1]))

    def __str__(self) -> str:
        flowStr = 'Łącze '
        for s in self.path:
            flowStr += s + '-'
        flowStr = flowStr[0:-1] + " (" + str(self.allocatedBw) + " Mb/s)"
        return flowStr

def createGraph():
    """Using the data imported from topo.json at app start we create NetworkX nodes and edges to create a graph of our topology."""
    global G
    G = nx.Graph()
    G.add_nodes_from(S)
    for start, end, delay, bw in E:
        bw_weight = ((1 / bw) ** 2) * delay ** 0.5
        G.add_edge(start, end, delay=delay, bw=bw_weight, availablebw = bw, maxBw = bw)

def znajdzSciezke(x, y, weight_type):
    """Using the dijkstra path finding algorithm provided from the NetworkX library this method finds the optimal path between host x and y.
    To do this we use the weight_type specified by the user which can either be "delay" or "bw"."""
    try:
        path = nx.dijkstra_path(G, x, y, weight=weight_type)
    except(networkx.exception.NetworkXNoPath):
        print("brak połączenia miedzy " + x + " i " + y)
        pass
    return path

def takeInput():
    """
    This method takes input from the user required to create a new Flow between any two hosts.
     The method warns the user when he tries to allocate more bandwidth than the dijkstra found path has available.
    returns: calculated dijkstra path and the allocatedBw or None if user requested duplicate path or canceled creating Flow
    """
    print("Możesz stworzyć nowe łącze między hostami")
    while(True):
        A_Point = input("Wpisz nazwę hosta 1: ")
        if A_Point in S:
            break
        print("Błąd - Nie ma takiego hosta")
    
    while(True):        
        B_Point = input("Wpisz nazwę hosta 2: ")
        if B_Point == A_Point:
            print('Błąd - nie możesz połączyć hosta z samym sobą')
        elif B_Point in S:
            break
        else:
            print("Błąd - nie ma takiego hosta")
    
    for flow in F:
        if flow.checkIfDuplicate(A_Point, B_Point):
            print('Błąd - Istnieje już łącze między tymi hostami')
            return None, None

    while(True):
        choice1 = input('Czy dla tego łącza priorytetem jest mniejsze opóźnienie czy większa przepustowość? [delay/bw]: ')
        if choice1 == 'delay' or choice1 == 'bw':
            break
        else:
            print('Błąd - niespodziewana odpowiedź')

    while(True):
        try:
            bwRequested = float(input("Jaką maksymalną przepustowość potrzebujesz? [w Mb/s]: "))
            assert(bwRequested > 0)
            break
        except:
            print("Błąd - wpisano niepoprawną wartość")

    path = znajdzSciezke(A_Point, B_Point, choice1)
    for i in range(len(path)-1):
        if G.edges[path[i], path[i+1]]['availablebw'] < bwRequested:
            while(True):
                choice2 = input('Aplikacja nie jest w stanie zagwarantować żądanej przepustowości łącza.\nCzy chcesz kontynuować? [t/n]: ')
                if choice2 == 't':
                    break
                elif choice2 == 'n':
                    return None, None
                else:
                    print('Błąd - niespodziewana odpowiedź')
            break
    
    return path, bwRequested

def postToONOS(request):
    """This method sends a POST request to ONOS with json formatted data containing all FlowRules required to create a working link between any two hosts.

    Prints the ONOS Response code (200 if succesful).
    
    Stores the json response from ONOS containing the assigned flowIds to our new Flow object."""
    headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    }

    response = requests.post('http://mininet:8181/onos/v1/flows', headers=headers, data=request, auth=('karaf', 'karaf'))
    print('\nOdpowiedź kontrolera ONOS:')
    print(response)
    
    F[-1].setFlowDict(response.json())

def fillTemplate(id, port, src_ip, dst_ip):
    """This method fills our FlowRule template imported from template.json with the necessary data.
    
    Returns: One complete json flow rule"""
    filling = template
    filling = filling.replace("#id#", id)
    filling = filling.replace("#port#", str(port))
    filling = filling.replace("#ip1#", dst_ip)
    filling = filling.replace("#ip2#", src_ip)
    return json.loads(filling)

def findNeighborPort(s, n):
    """This method returns the port assigned to a neighboring Node provided their IDs which is equal to their topo.json key (order of appearence) and S list index."""
    for neighbor in topoData['switches'][s]['neighbors']:
        if neighbor['key'] == n:
            return neighbor['port']

def writePath(path):
    """This method converts the dijkstra calculated path into a json request using the fillTemplate method.
    
    Returns: json data ready to be sent to ONOS"""
    flows = {"flows": []}
    src_key = S.index(path[0])
    dst_key = S.index(path[-1])

    for i in range(len(path)):
        s_id = S.index(path[i])

        if i != 0 and i != len(path) - 1:
            n_id = S.index(path[i+1])
            port = findNeighborPort(s_id, n_id)
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][src_key]['ip'], topoData['switches'][dst_key]['ip']))
            n_id = S.index(path[i-1])
            port = findNeighborPort(s_id, n_id)
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][dst_key]['ip'], topoData['switches'][src_key]['ip']))

        elif i == 0:
            n_id = S.index(path[i+1])
            port = findNeighborPort(s_id, n_id)
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][src_key]['ip'], topoData['switches'][dst_key]['ip']))
            port = 1
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][dst_key]['ip'], topoData['switches'][src_key]['ip']))

        elif i == len(path) - 1:
            n_id = S.index(path[i-1])
            port = 1
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][src_key]['ip'], topoData['switches'][dst_key]['ip']))
            port = findNeighborPort(s_id, n_id)
            flows['flows'].append(fillTemplate(topoData['switches'][s_id]['id'], port, topoData['switches'][dst_key]['ip'], topoData['switches'][src_key]['ip']))

    postRequest = json.dumps(flows, indent=2)
    newFlow = Flow(path)
    F.append(newFlow)
    return postRequest

def reduceAvailableBw(path, bwReq):
    """This method looks at the generated path and iterates over it to reduce the availableBw in created Flow objects"""
    smallestAvailable = G.edges[path[0], path[1]]['availablebw']
    for i in range(len(path) - 1):
        smallestAvailable = min(G.edges[path[i], path[i+1]]['availablebw'], smallestAvailable)
    smallestAvailable = min(bwReq, smallestAvailable)

    F[-1].setAllocatedBw(smallestAvailable)

    for i in range(len(path) - 1):
        G.edges[path[i], path[i+1]]['availablebw'] -= smallestAvailable
        G.edges[path[i], path[i+1]]['bw'] = ((1 / (G.edges[path[i], path[i+1]]['availablebw'] + 0.01)) ** 2) * G.edges[path[i], path[i+1]]['delay'] ** 0.5

def addAvailableBw(path, bw):
    """Does the opposite of the reduceAvailableBw function, meaning it adds the availableBw back to the Flow objects"""
    for i in range(len(path) - 1):
        G.edges[path[i], path[i+1]]['availablebw'] += bw
        G.edges[path[i], path[i+1]]['bw'] = ((1 / (G.edges[path[i], path[i+1]]['availablebw'] + 0.01)) ** 2) * G.edges[path[i], path[i+1]]['delay'] ** 0.5

def pauseOutput():
    print("\nWciśnij dowolny klawisz aby kontynuować...")
    msvcrt.getch()  # Wait for any key press (Windows specific)

def interface():
    """Main function of the program, runs the user interface and allows for choosing operations.
    
    1 - Creating a new Flow between any two hosts.
    
    2 - Showing all active Flows.
    
    3 - Listing all available links between switches similar to the "links" command in mininet.
    
    4 - Deleting any created Flow by providing it's ID from operation 2.
    
    5 - Exiting the program allowing the user to either delete all flows or keep them running."""
    while True:
        #os.system('cls')
        choice = input('Wybierz opcję:\n1. Stwórz nowe łącze\n2. Wyświetl aktualnie działające łącza\n3. Wyświetl połączenia i nieużywane przepustowości\n4. Usuń istniejące łącze\n5. Zakończ działanie aplikacji\n: ')
        #os.system('cls')
        if choice == '1':
            path, bwReq = takeInput()
            if path != None:
                postToONOS(writePath(path))
                reduceAvailableBw(path, bwReq)
                print('Stworzona ścieżka:')
                print(path)

        elif choice == '2':
            if len(F) == 0:
                print('\nBrak aktywnych łącz.')
            else:
                print('\nAktywne łącza:')
                for i, flow in enumerate(F):
                    print(str(i+1) + '. ' + str(flow))

        elif choice == '3':
            print('\nDostępne połączenia:')
            for i, edge in enumerate(E):
                print(str(i+1) + '. ' + edge[0] + '-' + edge[1] + ' (' + str(G.edges[edge[0],edge[1]]['availablebw']) + ' Mb/s)')

        elif choice == '4':
            while True:
                if len(F) == 0:
                    print('\nBrak aktywnych łącz.')
                    break
                try:
                    delFlow = int(input('Wprowadź numer łącza które chcesz usunąć: '))
                except:
                    print('Błąd - niespodziewana wartość')
                    continue
                if delFlow <= 0 or delFlow > len(F):
                    print('Błąd - nieistniejący numer łącza')
                    continue
                break
            print('\nOdpowiedź kontrolera ONOS:')
            F.pop(delFlow - 1).deleteFlow()

        elif choice == '5':
            while True:
                exitChoice = input('Czy na pewno chcesz wyłączyć aplikację? [t/n]: ')
                if exitChoice == 't':
                    exitChoice2 = input('Czy chcesz usunąć wszystkie łącza? [t/n]: ')
                    if exitChoice2 == 't':
                        for flow in F:
                            flow.deleteFlow()
                        sys.exit()
                    elif exitChoice2 == 'n':
                        sys.exit()
                elif exitChoice == 'n':
                    break
                else:
                    print('Błąd - nieoczekiwana odpowiedź')
                    continue
                break

        else:
            print('Błąd - nieoczekiwana odpowiedź')
        pauseOutput()


if __name__ == "__main__":
    createGraph()
    try:
        while(True):
            interface()
    except:
        for f in F:
            f.deleteFlow()