import json
from os import error
import os
from random import random
import time

from numpy.lib.npyio import save
from pcn.config import Config
from pcn.model import AttackModel, PcnModel
import sys
from pcn.server import server
from pcn.status import FeeConType, NodeType  # noqa
import argparse


def visulize():
    server.launch()


def fee_con_test(
    test_no,
    con_agent,
    num_of_steps=Config.SIM_STEPS,
    num_of_agents=Config.DEFAULT_N,
    fee_con=FeeConType.MPC_FEE,
    fee_con_params=Config.PARAMS_MPC
):

    # monitored
    model = PcnModel(
        id=(test_no, 0, 0),
        num_of_steps=num_of_steps,
        num_of_agents=num_of_agents,
        load_network=False,
        load_tx=False,
        store_network=True,
        store_tx=True
    )
    model.set_fee_con(con_agent, fee_con, fee_con_params)
    model.run_model()


def get_exhasusted(model, exhaustion):
    ex = [(k, sum([p[0] for p in v.values()]))
          for k, v in exhaustion.items()]
    ex_sorted = sorted(ex, key=lambda x: x[1], reverse=True)
    return [int(n[0]) for n in ex_sorted if model.network.get_node_type(
        int(n[0])) == NodeType.INTERMEDIARY]


def test(
    test_no,
    num_of_models=Config.MODELS_PER_TEST,
    num_of_steps=Config.SIM_STEPS,
    num_of_agents=Config.DEFAULT_N,
    num_fee_con = 1
):

    for m in range(num_of_models):
        print("Model", m, "started.")

        # STATIC FEE
        model = PcnModel(
            id=(test_no, m, 0),
            load_network=False,
            load_tx=False,
            store_network=True,
            store_tx=True,
            num_of_steps=num_of_steps,
            num_of_agents=num_of_agents
        )
        model.set_fee_con_rest([], FeeConType.STATIC_FEE, None)
        model.run_model()

        exhaustion = read_file_1(test_no, m, 0, '0_'+Config.FILE_EXHAUSTION)
        fee_con_agents = get_exhasusted(model, exhaustion)
        no_monitor = min(len(fee_con_agents), num_fee_con)
        fee_con_agents = fee_con_agents[:no_monitor]
        print("Controlled Model", m, "started with", fee_con_agents)

        # MPC FEE
        model = PcnModel(
            id=(test_no, m, 1),
            num_of_steps=num_of_steps,
            num_of_agents=num_of_agents,
            load_network=True,
            load_tx=True,
            store_network=False,
            store_tx=False
        )
        model.set_fee_con(fee_con_agents, FeeConType.MPC_FEE,
                          Config.PARAMS_MPC)
        model.set_fee_con_rest(fee_con_agents, FeeConType.STATIC_FEE, None)
        model.run_model()

        # MPC FEE
        model = PcnModel(
            id=(test_no, m, 2),
            num_of_steps=num_of_steps,
            num_of_agents=num_of_agents,
            load_network=True,
            load_tx=True,
            store_network=False,
            store_tx=False
        )
        model.set_fee_con(
            fee_con_agents, FeeConType.OPTIMIZEDFEE, Config.PARAMS_OF)
        model.set_fee_con_rest(fee_con_agents, FeeConType.STATIC_FEE, None)
        model.run_model()

        # DATA COMPARE
        files = [Config.FILE_EXHAUSTION,
                 Config.FILE_FEE, Config.FILE_EX_FAILURES]
        stat = {a: {} for a in fee_con_agents}

        for f in files:
            data0 = read_file_1(test_no, m, 0, '0_'+f)
            data1 = read_file_1(test_no, m, 1, '1_'+f)
            data2 = read_file_1(test_no, m, 1, '2_'+f)

            for agent in fee_con_agents:
                stat[agent].update({
                    f[:-5]: (data0.get(str(agent), {}),
                             data1.get(str(agent), {}), data2.get(str(agent), {}))
                })
                if f != Config.FILE_EXHAUSTION:
                    stat[agent].update({
                        f[:-5]+'_total': (sum(list(data0.get(str(agent), {}).values())),
                                sum(list(data1.get(str(agent), {}).values())),
                                sum(list(data2.get(str(agent), {}).values()))
                        )
                    })

        write_file_1(test_no, m, 0, Config.FILE_STAT, stat)


def read_file_1(test_no, model_no, save_no, file_name):
    file = Config.file_path((test_no, model_no, save_no), file_name)
    with open(file, 'r') as file_object:
        for i, line in enumerate(file_object):
            return json.loads(line)


def write_file_1(test_no, model_no, save_no, file_name, data):
    file = Config.file_path((test_no, model_no, save_no), file_name)
    json_object = json.dumps(data)
    with open(file, 'w') as file_object:
        file_object.write(json_object)


def repeat(
    test_no,
    model_no,
    save_no,
    steps,
    fee_con_type,
    fee_con_params,
    fee_con_agents=[],
    attack_model=None,
    wait=True,
    out_data=[]
):

    model = PcnModel(
        id=(test_no, model_no, save_no),
        load_network=True,
        load_tx=True,
        store_network=False,
        store_tx=False,
        num_of_steps=steps,
        num_of_agents=None,  # do not know
        attack_model=attack_model
    )
    if attack_model:
        attack_model.engage_victim(model)
        attack_model.engage_random(model,3)


    print("setting fee controller", fee_con_agents)

    model.set_fee_con(fee_con_agents, fee_con_type, fee_con_params)
    model.set_fee_con_rest(fee_con_agents, FeeConType.STATIC_FEE, None)
    if not len(out_data):
        out_data = fee_con_agents

    model.run_model()

    output = {}
    for agent in out_data:
        output[agent] = {}
        files = [Config.FILE_EXHAUSTION,
                 Config.FILE_FEE, Config.FILE_EX_FAILURES]
        for file in files:
            # read data from stat file -- initial run
            data = read_file_1(test_no, model_no, save_no,
                               str(save_no)+'_'+file)
            output[agent].update({file[:-5]: data.get(str(agent),{})})
            if file != Config.FILE_EXHAUSTION:
                output[agent].update({file[:-5]+'_total': sum(list(data.get(str(agent),{}).values()))})


    write_file_1(test_no, model_no, save_no, str(
        save_no)+'_' + 'out.json', output)

    if wait:
        input('print any key to continue')


def attack(test_no, num_of_steps, num_of_agents):
    test(
        test_no,
        num_of_models=1,
        num_of_steps=num_of_steps,
        num_of_agents=num_of_agents
    )
    attack_model = AttackModel()

    # read data from stat file -- initial run
    stat = read_file_1(test_no, 0, 0, Config.FILE_STAT)
    fee_con_agents = list([int(a) for a in stat.keys()])
    amounts = [0, 20, 40, 60, 80, 100, 120]
    for i in range(len(amounts)):
        attack_model.set_amount(amounts[i])
        repeat(test_no, 0, (i+3+0.1), num_of_steps,
               fee_con_type=FeeConType.STATIC_FEE,
               fee_con_params=None,
               attack_model=attack_model,
               victim=fee_con_agents[0],
               out_data=fee_con_agents[:1],
               wait=False
               )
        repeat(test_no, 0, (i+3+0.2), num_of_steps,
               fee_con_type=FeeConType.MPC_FEE,
               fee_con_params=Config.PARAMS_MPC,
               fee_con_agents=fee_con_agents,
               attack_model=attack_model,
               victim=fee_con_agents[0],
               wait=False
               )
        repeat(test_no, 0, (i+3+0.3), num_of_steps,
               fee_con_type=FeeConType.OPTIMIZEDFEE,
               fee_con_params=Config.PARAMS_OF,
               fee_con_agents=fee_con_agents,
               attack_model=attack_model,
               victim=fee_con_agents[0],
               wait=False
               )
        

def robust_test(test_no, model_no, save_no, num_of_steps):

    # read data from stat file -- initial run
    stat = read_file_1(test_no, model_no, 0, Config.FILE_STAT)
    fee_con_agents = list([int(a) for a in stat.keys()])
    amounts = [10,20,30,40,50]
    for i in range(len(amounts)):
        Config.ADJUST_AMOUNT = amounts[i]
        repeat(test_no, model_no, (i+save_no+0.1), num_of_steps,
               fee_con_type=FeeConType.STATIC_FEE,
               fee_con_agents=fee_con_agents,
               fee_con_params=None,
               wait=False,
               )
        repeat(test_no, model_no, (i+save_no+0.2), num_of_steps,
               fee_con_type=FeeConType.MPC_FEE,
               fee_con_params=Config.PARAMS_MPC,
               fee_con_agents=fee_con_agents,
               wait=False,
               )
        repeat(test_no, model_no, (i+save_no+0.3), num_of_steps,
               fee_con_type=FeeConType.OPTIMIZEDFEE,
               fee_con_params=Config.PARAMS_OF,
               fee_con_agents=fee_con_agents,
               wait=False,
               )

def get_rich(data):
    l = {}
    for k,v in data.items():
        out = k.split('-')[1]
        l[out] = l.get(out,0) + v 
    ls = sorted(l.items(), key=lambda kv: kv[1],reverse=True)
    return ls[0][0],ls[0][1]


def get_victim_channel(test,model):
    file = 'data/'+str(test)+'/'+str(model)+'/0_fee.json'
    with open(file, "r") as file_object:
        for i, line in enumerate(file_object):
            nodes = {}
            data = json.loads(line)
            for n, fees in data.items():
                nodes[n] = get_rich(fees)
            ls = sorted(nodes.items(), key=lambda kv: kv[1][1],reverse=True)
            return int(ls[0][0]),int(ls[0][1][0])

def repeat_attack(subdir, test_no, model_no, save_no, steps):

    # read data from stat file -- initial run
    attack_model = AttackModel()
    victim,rich_peer = get_victim_channel(test_no,model_no)
    print('Attack:',victim,rich_peer)
    attack_model.set_victim(victim,rich_peer)
    amounts = [0, 10, 20, 30, 40, 50]

    for i in range(len(amounts)):
        attack_model.set_amount(amounts[i])
        repeat(test_no, model_no, save_no+i+0.1, steps,
                   fee_con_agents=[victim],
                   attack_model=attack_model,
                   fee_con_type=FeeConType.STATIC_FEE,
                   fee_con_params=None,
                   wait=False
                   )
        repeat(test_no, model_no, save_no+i+0.2, steps,
                   fee_con_agents=[victim],
                   attack_model=attack_model,
                   fee_con_type=FeeConType.MPC_FEE,
                   fee_con_params=Config.PARAMS_MPC,
                   wait=False
                   )
        repeat(test_no, model_no, save_no+i+0.3, steps,
                   fee_con_agents=[victim],
                   attack_model=attack_model,
                   fee_con_type=FeeConType.OPTIMIZEDFEE,
                   fee_con_params=Config.PARAMS_OF,
                   wait=False
                   )



if sys.argv[1] == "-v" and len(sys.argv) > 1:
    server.launch()
elif sys.argv[1] == "-t" and len(sys.argv) > 5:
    test_no = int(sys.argv[2])
    num_of_models = int(sys.argv[3])
    num_of_steps = int(sys.argv[4])
    num_of_agents = int(sys.argv[5])
    test(
        test_no=test_no,
        num_of_models=num_of_models,
        num_of_steps=num_of_steps,
        num_of_agents=num_of_agents
    )
elif sys.argv[1] == "-all" and len(sys.argv) > 5:
    test_no = int(sys.argv[2])
    num_of_models = int(sys.argv[3])
    num_of_steps = int(sys.argv[4])
    num_of_agents = int(sys.argv[5])
    test(
        test_no=test_no,
        num_of_models=num_of_models,
        num_of_steps=num_of_steps,
        num_of_agents=num_of_agents,
        num_fee_con=-1
    )
elif sys.argv[1] == "-r" and len(sys.argv) > 5:
    test_no = int(sys.argv[2])
    model_no = int(sys.argv[3])
    save_no = int(sys.argv[4])
    steps = int(sys.argv[5])

    # read data from stat file -- initial run
    stat = read_file_1(test_no, model_no, 0, Config.FILE_STAT)
    fee_con_agents = list([int(a) for a in stat.keys()])
    repeat(test_no, model_no, save_no, steps, fee_con_type=FeeConType.MPC_FEE,
           fee_con_params=Config.PARAMS_MPC, fee_con_agents=fee_con_agents)

elif sys.argv[1] == "-ra" and len(sys.argv) > 4:
    test_no = int(sys.argv[2])
    save_no = int(sys.argv[3])
    steps = int(sys.argv[4])
    dir = 'data/'+str(test_no)+'/'
    subdirs = [x[0] for x in os.walk(dir)][1:]

    for subdir in subdirs:
        print("attacking "+subdir)
        try:
            file_no = int(subdir.split('/')[2])
            repeat_attack(subdir=subdir, test_no=test_no, model_no=file_no, save_no=save_no, steps=steps)
        except Exception as e:
            print(subdir,test_no,file_no,e)

elif sys.argv[1] == "-a" and len(sys.argv) > 4:
    test_no = int(sys.argv[2])
    num_of_steps = int(sys.argv[3])
    num_of_agents = int(sys.argv[4])
    attack(test_no, num_of_steps, num_of_agents)

elif sys.argv[1] == "-rt" and len(sys.argv) > 4:
    test_no = int(sys.argv[2])
    save_no = int(sys.argv[3])
    num_of_steps = int(sys.argv[4])
    dir = 'data/'+str(test_no)+'/'
    subdirs = [x[0] for x in os.walk(dir)][1:]

    for subdir in subdirs:
        print("attacking "+subdir)
        try:
            file_no = int(subdir.split('/')[2])
            robust_test(test_no, file_no, save_no, num_of_steps)
        except Exception as e:
            print("error",subdir,test_no,file_no,e)

elif sys.argv[1] == "-rp" and len(sys.argv) > 4:
    test_no = int(sys.argv[2])
    model_no = int(sys.argv[3])
    steps = int(sys.argv[4])

    # read data from stat file -- initial run
    stat = read_file_1(test_no, model_no, 0, Config.FILE_STAT)
    fee_con_agents = list([int(a) for a in stat.keys()])

    for i in range(10):
        params = Config.PARAMS_MPC
        params['w_m'] = (i+1)/10
        repeat(test_no, model_no, i+1, steps, fee_con_agents=fee_con_agents,
               fee_con_params=params)  # only one model
elif sys.argv[1] == "-feecon" and len(sys.argv) > 5:
    test_no = int(sys.argv[2])
    con_agent = int(sys.argv[3])
    num_of_steps = int(sys.argv[4])
    num_of_agents = int(sys.argv[5])
    fee_con_test(
        test_no=test_no,
        con_agent=list(range(num_of_agents)),
        num_of_steps=num_of_steps,
        num_of_agents=num_of_agents
    )
else:
    print("Invalid arguments.")
