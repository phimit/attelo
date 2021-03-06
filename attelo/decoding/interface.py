'''
Common interface that all decoders must implement
'''

from __future__ import print_function
from abc import ABCMeta, abstractmethod
from six import with_metaclass

# pylint: disable=abstract-class-not-used, abstract-class-little-used
# pylint: disable=too-few-public-methods


class Decoder(with_metaclass(ABCMeta, object)):
    '''
    A decoder is a function which given a probability distribution (see below)
    and some control parameters, returns a sequence of predictions.

    Most decoders only really return one prediction in practice, but some,
    like the A* decoder might have able to return a ranked sequence of
    the "N best" predictions it can find

    We have a few informal types to consider here:

        - a **link** (`(string, string, string)`) represents a link
          between a pair of EDUs. The first two items are their
          identifiers, and the third is the link label

        - a **proposed link** (`(string, string, float, string)`)
          is a link with a probability attached

        - a **prediction** is morally a set (in practice a list) of links

        - a **distribution** is morally a set of proposed links
    '''

    @abstractmethod
    def decode(self, prob_distrib):
        '''
        :param prob_distrib: the proposed links that we would like
                             to decode over
        :type prob_distrib: [(string, string, float, string)]

        :rtype: [ [(string,string,string)] ]
        '''
        raise NotImplementedError
