
# Sala (PCN Simulator)


### Introduction

Sala is an agent based simulator which was developed to simulate the function of a payment channel network. It models nodes as agents who interact with each other to execute payments. Agents establish and maintain payment channels among peer nodes and then initiate, receive, and mediate the transactions. We can control the fee strategy and monitor the revenues and balances of those nodes. In the implementation of Sala, we use Mesa library\footnote{mesa.readthedocs.io} to model the PCN nodes as agents. The overall process of Sala is as follows. 

### Components

![](https://github.com/anupasm/SALA/blob/master/res/arch.png)

Sala consists of a collection of configurable modules and components. The **network module** initializes the payment nodes and channels as a graph-based network. Then the **transaction module** generates the transactions for the network. Both accommodate the different behaviours of three types of agents in PCN (i.e. payers, payees and payment mediators). Further, they can act independently or work on a given set of data, which allows repeating the experiments on the same data set (i.e. transactions). Those algorithms are customizable, either probabilistic or static (e.g. assigning channel capacity, payer and payee selection). The **communication layer** is responsible for the agent communication of transaction information. Additionally, **data collection** and **visualization components** operate along with all the operations to collect and display the real-time network and its data. 

### Process

Once the nodes and channels are determined, the system advances step by step, and in each stage, agents act simultaneously. With the help of the communication layer, an agent can initiate a payment, forward the transaction, temporarily lock up the respective transaction amounts, provide the valid secret (i.e. payee), verify the validity, pass back the transaction and update the balances. In the meantime, they also monitor the expiration times included in the transactions. They can also be configured to restart the transaction on an alternate path in case of failure (i.e. timeout, insufficient balance, invalid secret). 

### Speciality

- Sala is configurable to model selected agents to act according to the customized instructions. For example, we can set different fee controllers for the agents to determine their charge according to the circumstantial parameters (i.e. transaction amount, balance). 
- There is a behaviour component to model the behaviour of malicious agents who can engage with nodes and inject bogus transactions.


