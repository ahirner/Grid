from .. import base
from ..services.broadcast_known_workers import BroadcastKnownWorkersService
from ..services.whoami import WhoamiService
from ..lib import utils
from threading import Thread
import json
from bitcoin import base58
import base64
import random

class GridWorker():

    def __init__(self):
        # super().__init__('worker')


        self.api = utils.get_ipfs_api()
        peer_id = self.api.config_show()['Identity']['PeerID']
        self.id = f'{peer_id}'

        # switch to this to make local develop work
        # self.id = f'{mode}:{peer_id}'
        self.subscribed_list = []
        

        # LAUNCH SERVICES - these are non-blocking and run on their own threads

        # all service objects will live in this dictionary

        self.services = {}

        # this service serves the purpose of helping other nodes find out about nodes on the network.
        # if someone queries the "list_worker" channel - it'll send a message directly to the querying node
        # with a list of the OpenMined nodes of which it is aware.
        self.services['broadcast_known_workers'] = BroadcastKnownWorkersService(self)

        # WHOMAI
        self.services['whoami_service'] = WhoamiService(self)

    def get_openmined_nodes(self):
        """
        This method returns the list of known openmined workers on the newtork.
        Note - not all workers are necessarily "compute" workers. Some may only be anchors
        and will ignore any jobs you send them.
        """

        nodes = self.api.pubsub_peers('openmined')['Strings']
        if(nodes is not None):
            return nodes
        else:
            return []

    def get_nodes(self):
        nodes =  self.api.pubsub_peers()['Strings']
        if(nodes is not None):
            return nodes
        else:
            return []

    def publish(self, channel, message):
        """
        This method sends a message over an IPFS channel. The number of people who receive it is
        purely based on the number of people who happen to be listening.
        """

        if isinstance(message, dict) or isinstance(message, list):
            self.api.pubsub_pub(topic=channel, payload=json.dumps(message))
        else:
            self.api.pubsub_pub(topic=channel, payload=message)

    def request_response(self,channel,message,response_handler):
        """
        This method makes a request over a channel to a specific node and
        will hang until it receives a response from that node. Note that
        the channel used for the response is random.
        """


        random_channel = self.id + "_" + str(random.randint(0, 1e10))

        def send():
            self.publish(channel=channel,message=[message,random_channel])

        return self.listen_to_channel_sync(random_channel, response_handler, send)


    def listen_to_channel_sync(self, *args):
        """
        Synchronous version of listen_to_channel
        """

        return self.listen_to_channel_impl(*args)

    def listen_to_channel(self, *args):
        """
        Listens for IPFS pubsub sub messages asynchronously.

        This function will create the listener and call back your handler
        function on a new thread.
        """
        t1 = Thread(target=self.listen_to_channel_impl, args=args)
        t1.start()

    def listen_to_channel_impl(self, channel, handle_message,
                               init_function=None, ignore_from_self=False):
        """
        Do not call directly.  Use listen_to_channel or listen_to_channel_sync instead.
        """

        first_proc = True

        if channel not in self.subscribed_list:
            
            # print(f"SUBSCRIBING TO {channel}")
            new_messages = self.api.pubsub_sub(topic=channel, stream=True)
            self.subscribed_list.append(channel)

        else:
            print(f"ALREADY SUBSCRIBED TO {channel}")
            return

        for m in new_messages:
            if init_function is not None and first_proc:
                init_function()
                first_proc = False

            message = self.decode_message(m)
            if message is not None:
                fr = base58.encode(message['from'])

                if not ignore_from_self or fr != self.id:
                    out = handle_message(message)
                    if(out is not None):
                        return out
                else:
                    print("ignored message from self")

                # if(message is not None):
                #    if handle_message is not None:
                #        out = handle_message(message)
                #        if (out is not None):
                #            return out
                #        else:
                #            return message
                #    else:
                #        return message

    def decode_message(self, encoded):
        if('from' in encoded):
            decoded = {}
            decoded['from'] = base64.standard_b64decode(encoded['from'])
            decoded['data'] = base64.standard_b64decode(
                encoded['data']).decode('ascii')
            decoded['seqno'] = base64.standard_b64decode(encoded['seqno'])
            decoded['topicIDs'] = encoded['topicIDs']
            decoded['encoded'] = encoded
            return decoded
        else:
            return None
