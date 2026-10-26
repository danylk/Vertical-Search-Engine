import math
import sys
from collections import defaultdict

def eval_print(QueryID, num_ret, num_rel, num_rel_ret, avg_prec, cutoffs, nDCG, prec_at_cutoffs, recall_at_cutoffs, f1_at_cutoffs, r_prec):
    print("\nQueryid (Num):    %5d\n" % QueryID)
    print("Total number of documents over all queries\n")
    print("    Retrieved:    %5d\n" % num_ret)
    print("    Relevant:     %5d\n" % num_rel)
    print("    Rel_ret:      %5d\n" % num_rel_ret)
    print("Average precision (non-interpolated) for all rel docs(averaged over queries)\n")
    print("                  %.4f\n" % avg_prec)
    print("@k:\n")
    for i in range(len(cutoffs)):
        print("  At    {} docs:   nDCG - {:.4f}, Precision - {:.4f}, Recall - {:.4f}, F1 - {:.4f}\n".format(cutoffs[i], nDCG[i], prec_at_cutoffs[i], recall_at_cutoffs[i], f1_at_cutoffs[i]))
    print("R-Precision (precision after R (= num_rel for a query) docs retrieved):\n")
    print("    Exact:        %.4f\n" % r_prec)

def run():
    print_all_queries = 0
    qrel_file = None
    trec_file = None
    QREL_data = None
    qrel = defaultdict(dict)
    trec = defaultdict(dict)
    num_rel = {}
    tot_num_ret = 0
    tot_num_rel = 0
    tot_num_rel_ret = 0

    cutoffs = [5, 10, 20, 50, 100]
    sum_prec_at_cutoffs = [0] * len(cutoffs)
    sum_recall_at_cutoffs = [0] * len(cutoffs)
    sum_f1_at_cutoffs = [0] * len(cutoffs)
    sum_nDCG = [0] * len(cutoffs)
    avg_prec_at_cutoffs = [0.0] * len(cutoffs)
    avg_recall_at_cutoffs = [0.0] * len(cutoffs)
    avg_f1_at_cutoffs = [0.0] * len(cutoffs)
    avg_nDCG = [0.0] * len(cutoffs)
    sum_avg_prec = 0
    sum_r_prec = 0

    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage:  trec_eval [-q] <qrel_file> <trec_file>\n\n")
        return

    if len(sys.argv) == 3:
        qrel_file = sys.argv[1]
        trec_file = sys.argv[2]
    else:
        qrel_file = sys.argv[2]
        trec_file = sys.argv[3]
        print_all_queries = 1

    try:
        with open(qrel_file, 'r') as f:
            QREL_data = f.read().split("\n")
    except:
        print("Could not open qrel file")

    for q in QREL_data:
        if q != "":
            QueryID, AssesorID, DocID, Grade = q.split()
            QueryID = int(QueryID)
            Grade = int(Grade)
            qrel[QueryID].update({DocID : Grade})
            num_rel[QueryID] = num_rel.get(QueryID, 0) + Grade

    try:
        with open(trec_file, 'r') as f:
            TREC_data = f.read().split("\n")
    except:
        print("Could not open trec file")

    for t in TREC_data:
        if t != "":
            QueryID, _, DocID, _, Score, _ = t.split()
            QueryID = int(QueryID)
            Score = float(Score)
            trec[QueryID].update({DocID : Score})

    num_topics = 0
    for QueryID in sorted(trec.keys()):
        if num_rel.get(QueryID) is None:
            continue

        num_topics += 1
        href = trec[QueryID]
        prec_list = [0.0] * 1001
        rec_list = [0] * 1001
        f1_list = [0] * 1001
        iDCG_list = [1] * 1001
        DCG_list = [0] * 1001
        nDCG_list = [0] * 1001

        for i in range(1, 1001):
            if i < num_rel.get(QueryID):
                iDCG_list[i] = iDCG_list[i - 1] + (1 / (math.log(i + 2, 2)))
            else:
                iDCG_list[i] = iDCG_list[i - 1]

        num_ret = 0
        num_rel_ret = 0
        sum_prec = 0

        for DocID in sorted(href, key = lambda x: (-href[x], x)):
            num_ret += 1
            rel = qrel.get(QueryID, {}).get(DocID, None)
            if rel:
                sum_prec += rel * (1 + num_rel_ret) / num_ret
                num_rel_ret += rel
            prec_list[num_ret] = num_rel_ret / num_ret
            rec_list[num_ret] = num_rel_ret / num_rel.get(QueryID, 0)
            DCG_list[num_ret] = num_rel_ret
            nDCG_list[num_ret] = DCG_list[num_ret] / iDCG_list[num_ret]
            if ((num_rel_ret / num_ret) + (num_rel_ret / num_rel.get(QueryID, 0))) == 0:
                f1_list[num_ret] = 0
            else:
                f1_list[num_ret] = (2 * (num_rel_ret / num_ret) * (num_rel_ret / num_rel.get(QueryID, 0))) / ((num_rel_ret / num_ret) + (num_rel_ret / num_rel.get(QueryID, 0)))
            if num_ret >= 1000:
                break

        avg_prec = sum_prec / num_rel.get(QueryID, 0)

        final_recall = num_rel_ret / num_rel.get(QueryID, 0)

        final_DCG = num_rel_ret

        for i in range(num_ret + 1, 1001):
            prec_list[i] = num_rel_ret / i
            rec_list[i] = final_recall
            DCG_list[i] = final_DCG
            nDCG_list[i] = final_DCG / iDCG_list[i]

        prec_at_cutoffs = [prec_list[cutoff] for cutoff in cutoffs]
        recall_at_cutoffs = [rec_list[cutoff] for cutoff in cutoffs]
        f1_at_cutoffs = [f1_list[cutoff] for cutoff in cutoffs]
        nDCG = [nDCG_list[cutoff] for cutoff in cutoffs]

        if num_rel.get(QueryID, 0) > num_ret:
            r_prec = num_rel_ret / num_rel.get(QueryID, 0)
        else:
            int_num_rel = int(num_rel.get(QueryID, 0))  # Integer part.
            frac_num_rel = num_rel.get(QueryID, 0) - int_num_rel  # Fractional part.
            r_prec = (1 - frac_num_rel) * prec_list[int_num_rel] + frac_num_rel * prec_list[
                int_num_rel + 1] if frac_num_rel > 0 else prec_list[int_num_rel]

        max_prec = 0
        for i in range(1000, 0, -1):
            if prec_list[i] > max_prec:
                max_prec = prec_list[i]
            else:
                prec_list[i] = max_prec

        if print_all_queries == 1:
            eval_print(QueryID, num_ret, num_rel.get(QueryID, 0), num_rel_ret, avg_prec, cutoffs, nDCG, prec_at_cutoffs, recall_at_cutoffs, f1_at_cutoffs, r_prec)

        tot_num_ret += num_ret
        tot_num_rel += num_rel.get(QueryID, 0)
        tot_num_rel_ret += num_rel_ret

        for i in range(len(cutoffs)):
            sum_prec_at_cutoffs[i] += prec_at_cutoffs[i]
            sum_recall_at_cutoffs[i] += recall_at_cutoffs[i]
            sum_f1_at_cutoffs[i] += f1_at_cutoffs[i]
            sum_nDCG[i] += nDCG[i]

        sum_avg_prec += avg_prec
        sum_r_prec += r_prec

    print("Queries evaluated: %d\n" % num_topics)
    for i in range(len(cutoffs)):
        avg_prec_at_cutoffs[i] = sum_prec_at_cutoffs[i] / num_topics
        avg_recall_at_cutoffs[i] = sum_recall_at_cutoffs[i] / num_topics
        avg_f1_at_cutoffs[i] = sum_f1_at_cutoffs[i] / num_topics
        avg_nDCG[i] = sum_nDCG[i] / num_topics

    mean_avg_prec = sum_avg_prec / num_topics
    avg_r_prec = sum_r_prec / num_topics

    eval_print(num_topics, tot_num_ret, tot_num_rel, tot_num_rel_ret,
               mean_avg_prec, cutoffs, avg_nDCG, avg_prec_at_cutoffs, avg_recall_at_cutoffs, avg_f1_at_cutoffs, avg_r_prec)

if __name__ == "__main__":
    run()

