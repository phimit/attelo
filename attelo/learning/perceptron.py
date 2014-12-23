import sys
import time
from collections import defaultdict, namedtuple
from numpy import *
from numpy.linalg import norm

from attelo.edu import EDU, mk_edu_pairs

"""
TODO:
- expose PA-II C aggressiveness parameter
- add more principled scores to probs conversion (right now, we do just 1-norm weight normalization and use logit function)
- old problem with ('word_last_DU1', '?') and ('word_last_DU2', '?') features (not sure, this is still a problem...)
- add MC perc and PA for relation prediction.
- fold relation prediction into structured learning
"""

PerceptronArgs = namedtuple('PerceptronArgs', 'iterations averaging use_prob')


def is_perceptron_model(model):
    """
    If the model in question is somehow based on perceptrons
    """
    return model.name in ["Perceptron", "PassiveAggressive",\
                          "StructuredPerceptron", "StructuredPassiveAggressive"]


class Perceptron( object ):
    """ Vanilla binary perceptron learner """
    def __init__(self, meta_features, nber_it=10, avg=False, use_prob=False): 
        self.name = "Perceptron"
        self.meta_features = meta_features
        self.nber_it = nber_it
        self.avg = avg
        self.weights = None
        self.avg_weights = None
        self.orange_interface = None
        self.use_prob = use_prob
        return
    
    
    def __call__(self, orange_train_data):
        """ learn perceptron weights """
        interface = OrangeInterface( orange_train_data, self.meta_features )
        train_instances = interface.train_instance_generator()
        self.init_model( interface.get_feature_map() )
        self.learn( train_instances ) 
        self.orange_interface = interface
        return self
    

    def init_model( self, feature_map ):
        dim = len( feature_map )
        self.weights = zeros( dim, 'd' )
        self.avg_weights = zeros( dim, 'd' )
        return


    def learn( self, instances ):
        start_time = time.time()
        print >> sys.stderr, "-"*100
        print >> sys.stderr, "Training..."
        nber_it = self.nber_it
        if nber_it > 1:
            instances = list(instances)
        for n in range( nber_it ):
            print >> sys.stderr, "it. %3s \t" %n, 
            loss = 0.0
            t0 = time.time()
            inst_ct = 0
            for _, ref_cl, fv in instances:
                # print >> sys.stderr, ref_cl, fv
                # sys.stderr.flush()
                inst_ct += 1
                sys.stderr.write("%s" %"\b"*len(str(inst_ct))+str(inst_ct))
                pred_cl, score = self._classify( fv, self.weights )
                loss += self.update( pred_cl, ref_cl, fv, score )
            if inst_ct > 0:
                loss = loss / float(inst_ct)
            t1 = time.time()
            print >> sys.stderr, "\tavg loss = %-7s" %round(loss,6),
            print >> sys.stderr, "\ttime = %-4s" %round(t1-t0,3)
        elapsed_time = t1-start_time
        print >> sys.stderr, "done in %s sec." %(round(elapsed_time,3))
        return


    def update( self, pred, ref, fv, score, rate=1.0 ): 
        """ simple perceptron update rule"""
        error = (pred != ref)
        w = self.weights
        if error:
            w = w + rate * ref * fv
            self.weights = w
        if self.avg:
            self.avg_weights += w
        return int(error)

    

    def _classify( self, fv, w ):
        """ classify feature vector fv using weight vector w into
        {-1,+1}"""
        score = dot( w, fv )
        label = 1 if score >= 0 else -1
        return label, score


    def get_scores( self, orange_doc_instances ):
        interface = self.orange_interface
        doc_instances = interface.instance_generator( orange_doc_instances )
        scores = []
        w = self.avg_weights if self.avg else self.weights
        for edu_pair, _, fv in doc_instances:
            score = _score( w, fv, use_prob=self.use_prob )
            scores.append( (edu_pair[0], edu_pair[1], score, "unlabelled") )
        return scores









class PassiveAggressive( Perceptron ):
    """ Passive-Aggressive classifier in primal form. PA has a
	margin-based update rule: each update yields at least a margin
	of one (see defails below). Specifically, we implement PA-II
	rule for the binary setting (see Crammer et. al 2006). Default
	C=inf parameter makes it equivalent to simple PA.""" 

    def __init__( self, meta_features, nber_it=10, avg=False, use_prob=False, C=inf ):
        Perceptron.__init__(self, meta_features, nber_it=nber_it, avg=avg, use_prob=use_prob)
        self.name = "PassiveAggressive"
        self.aggressiveness = C 
        return


    def update( self, pred, ref, fv, score ): 
        """ PA-II update rule:
        w = w + t * y * x
        where: t = min {C, loss / ||x||**2}
               loss = 0  if margin >= 1.0
                      1.0 - margin  o.w.
               margin =  y (w . x)
        """
        w = self.weights
        C = self.aggressiveness
        margin = ref * score
        loss = 0.0 
        if margin < 1.0:
            loss = 1.0-margin
        tau = loss / float(norm(fv)**2)
        tau = min( C, tau )
        w = w + tau * ref * fv
        self.weights = w
        if self.avg:
            self.avg_weights += w
        return loss








class StructuredPerceptron( Perceptron ):
    """ Perceptron classifier (in primal form) for structured
    problems.""" 


    def __init__( self, meta_features, decoder, nber_it=10, avg=False, use_prob=False ): 
        Perceptron.__init__(self, meta_features, nber_it=nber_it, avg=avg, use_prob=use_prob)
        self.name = "StructuredPerceptron"
        self.decoder = decoder 
        return
    

    def __call__(self, orange_train_data):
        interface = OrangeInterface( orange_train_data, self.meta_features )
        train_instances = interface.train_instance_generator()
        self.init_model( interface.get_feature_map() )
        # group EDU pair instances by documents and build document
        # references
        doc2fvs = defaultdict(dict)
        doc2ref_graph = defaultdict(list)
        for edu_pair_inst in orange_train_data:
            doc_name = edu_pair_inst[self.meta_features.grouping].value
            edu_pair, label, fv = interface.instance_convertor( edu_pair_inst )
            edu1,edu2 = edu_pair
            doc2fvs[doc_name][edu1.id,edu2.id] = fv
            if label == 1:
                doc2ref_graph[doc_name].append( (edu1.id, edu2.id, "unlabelled") )
        # learn weights 
        self.learn( doc2fvs, doc2ref_graph ) 
        self.orange_interface = interface
        return self

                
    def learn( self, doc2fvs, doc2ref_graph ):
        start_time = time.time()
        print >> sys.stderr, "-"*100
        print >> sys.stderr, "Training struct. perc..."
        for n in range( self.nber_it ):
            print >> sys.stderr, "it. %3s \t" %n, 
            loss = 0.0
            t0 = time.time()
            inst_ct = 0
            for doc_id, fvs in doc2fvs.items():
                # print doc_id
                inst_ct += 1
                sys.stderr.write("%s" %"\b"*len(str(inst_ct))+str(inst_ct))
                # make prediction based on current weight vector
                predicted_graph = self._classify( fvs,
                                                  self.weights ) 
                # print doc_id,  predicted_graph 
                loss += self.update( predicted_graph,
                                     doc2ref_graph[doc_id],
                                     fvs)
            # print >> sys.stderr, inst_ct, 
            avg_loss = loss / float(inst_ct)
            t1 = time.time()
            print >> sys.stderr, "\tavg loss = %-7s" %round(avg_loss,6),
            print >> sys.stderr, "\ttime = %-4s" %round(t1-t0,3)
        elapsed_time = t1-start_time
        print >> sys.stderr, "done in %s sec." %(round(elapsed_time,3))
        return

        
    def update( self, pred_graph, ref_graph, fvs, rate=1.0 ): 
        # print "REF GRAPH:", ref_graph
        # print "PRED GRAPH:", pred_graph
        # print "INTER:", set(pred_graph) & set(ref_graph)
        w = self.weights
        # print "W in:", w
        error = 1-(len(set(pred_graph) & set(ref_graph))/float(len(ref_graph)))
        if error:
            ref_global_fv = zeros( len(w), 'd' )
            pred_global_fv = zeros( len(w), 'd' )
            for ref_arc in ref_graph:
                edu1_id, edu2_id, _ = ref_arc
                ref_global_fv = ref_global_fv + fvs[edu1_id, edu2_id]
            for pred_arc in pred_graph:
                edu1_id, edu2_id, _ = pred_arc
                pred_global_fv = pred_global_fv + fvs[edu1_id, edu2_id]
            # assert dot(ref_global_fv,w) <= dot(pred_global_fv,w), "Error: Ref graph should not have score higher than predicted graph!!!" 
            w = w + rate * ( ref_global_fv - pred_global_fv )
        self.weights = w
        if self.avg:
            self.avg_weights += w

        return error


    def _classify( self, fvs, weights ):
        """ return predicted graph """
        decoder = self.decoder
        scores = []
        for (edu1_id, edu2_id), fv in fvs.items():
            score = dot( weights, fv )
            # print "\t", edu1_id, edu2_id, score # , fv
            scores.append( ( EDU(edu1_id, 0, 0, None), # hacky
                             EDU(edu2_id, 0, 0, None),
                             score,
                             "unlabelled" ) )
        # print "SCORES:", scores
        pred_graph = decoder( scores, use_prob=False )
        return pred_graph


    def get_scores( self, orange_doc_instances ):
        interface = self.orange_interface
        doc_instances = interface.instance_generator( orange_doc_instances )
        scores = []
        w = self.avg_weights if self.avg else self.weights
        for edu_pair, _, fv in doc_instances:
            score = _score( w, fv, use_prob=self.use_prob )
            scores.append( (edu_pair[0], edu_pair[1], score, "unlabelled" ) )
        return scores



  



    
class StructuredPassiveAggressive( StructuredPerceptron ):
    """ Structured PA-II classifier (in primal form) for structured
    problems.""" 


    def __init__( self, meta_features, decoder, nber_it=10, avg=False, use_prob=False, C=inf ):
        StructuredPerceptron.__init__(self, meta_features, decoder, nber_it=nber_it, avg=avg, use_prob=use_prob)
        self.name = "StructuredPassiveAggressive"
        self.aggressiveness = C
        return



    def update( self, pred_graph, ref_graph, fvs, rate=1.0 ):
        """ PA-II update rule:
        w = w + t * Phi(x,y)-Phi(x-y^) 
        where: t = min {C, loss / ||Phi(x,y)-Phi(x-y^)||**2}
               loss = 0  if margin >= 1.0
                      1.0 - margin  o.w.
               margin =  w . ( Phi(x,y)-Phi(x-y^) )
        """
        w = self.weights
        C = self.aggressiveness
        # compute Phi(x,y) and Phi(x,y^)
        ref_global_fv = zeros( len(w), 'd' )
        pred_global_fv = zeros( len(w), 'd' )
        for ref_arc in ref_graph:
            edu1_id, edu2_id, _ = ref_arc
            ref_global_fv = ref_global_fv + fvs[edu1_id, edu2_id]
        for pred_arc in pred_graph:
            edu1_id, edu2_id, _ = pred_arc
            pred_global_fv = pred_global_fv + fvs[edu1_id, edu2_id]
        # find tau
        delta_fv = ref_global_fv-pred_global_fv
        margin = dot( w, delta_fv )
        loss = 0.0
        tau = 0.0
        if margin < 1.0:
            loss = 1.0-margin
        norme = norm(delta_fv)
        if norme != 0:
            tau = loss / float(norme**2)
        tau = min( C, tau )
        # update
        w = w + tau * delta_fv
        self.weights = w
        if self.avg:
            self.avg_weights += w
        error = 1-(len(set(pred_graph) & set(ref_graph))/float(len(ref_graph)))
        return error
    



    



class OrangeInterface( object ):

    def __init__(self, data, meta_features):
        self.__data = data
        self.__meta_features = meta_features
        self.set_feature_map()
        return

    def set_feature_map( self ): # FIXME: remove redundant features: True/False
        """ binarizing all features and construct feature-to-integer map """
        domain = self.__domain = self.__data.domain
        fmap = {} 
        pos = 0
        print >> sys.stderr, "# of orange features", len(domain.features)
        # print domain.features
        for feat in domain.features:
            # print feat.name
            if str(feat.var_type) == "Continuous":
                fmap[feat.name] = pos
                pos += 1
            elif str(feat.var_type) == "Discrete":
                for val in feat.values:
                    fmap[feat.name,val] = pos
                    pos += 1
            else:
                raise TypeError("Unsupported orange feature type: %s" %feat.var_type)
        print >> sys.stderr, "# of binarized features", len(fmap)
        self.__feature_map = fmap
        return


    def get_feature_map( self ):
        return self.__feature_map


    def get_edu_pair(self, orange_inst):
        return mk_edu_pairs(self.__meta_features, self.__domain)(orange_inst)
    

    def instance_convertor( self, orange_inst ):
        """ convert orange instance into feature vector """
        fmap = self.__feature_map
        fv = zeros( len(fmap) )
        classe = None
        edu_pair = self.get_edu_pair( orange_inst )
        for av in orange_inst:
            att_name = av.variable.name
            att_type = str(av.var_type)
            att_val = av.value
            # print "Type '%s': '%s'='%s'" %(att_type, att_name, att_val)
            # get class label (do not use it as feature :-))
            if att_name == self.__meta_features.label: 
                if av.value == "True":
                    classe = 1
                elif av.value == "False":
                    classe = -1
                else:
                    raise TypeError("Label attribute value should be boolean: %s" %av.value)
            else:
                # build feature vector by looking up the feature map
                if att_type == "Continuous":
                    fv[fmap[att_name]] = att_val
                elif att_type == "Discrete":
                    try:
                        fv[fmap[att_name,att_val]] = 1.0
                    except KeyError:
                        print >> sys.stderr, "Unseen feature:", (att_name,att_val) 
                else:
                    raise TypeError("Unknown feature type/value: '%s'/'%s'" %(att_type,av.value))
        # print "FV:", sum(fv), fv
        assert classe in [-1,1], "label (%s) not in {-1,1}" %classe
        return edu_pair, classe, fv


    def train_instance_generator( self ):
        return self.instance_generator( self.__data )
    
    
    def instance_generator( self, data ):
        for instance in data:
            yield self.instance_convertor( instance )

            


def _score( w_vect, feat_vect, use_prob=False ):
    s = dot( w_vect, feat_vect )
    if use_prob:
        s = logit( s )
    return s


def logit( score ):
    """ return score in [0,1], i.e., fake probability"""
    return 1.0/(1.0+exp(-score))
