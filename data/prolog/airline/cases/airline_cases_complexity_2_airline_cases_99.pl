flight_cost(258).
bag(2,49,33,25,53). bag(3,36,17,11,73). bag(4,37,17,11,79). bag(5,33,18,13,68).
bag(6,36,19,9,51). bag(7,36,18,9,62). bag(8,34,18,12,63). bag(9,36,15,12,99).
bag(10,35,18,11,51). bag(11,37,24,13,59).
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 200 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(3, 150). bag_fee(N, 200) :- N >= 4.
choose_two(List, F1, F2) :- append(_, [F1|Tail], List), member(F2, Tail).
ordered_list(F1, F2, Ordered) :-
    checked_bag_ids(All), select(F1, All, R1), select(F2, R1, R2), Ordered = [F1,F2|R2].
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, SF, SP) :-
    ( Idx =< 2 -> Kind = comp ; Kind = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Kind, Pen), Next is Idx+1,
    cost_bags(Bs, Next, FR, PR), SF is Fee+FR, SP is Pen+PR.
choice_cost(F1, F2, Total) :-
    ordered_list(F1, F2, Ord), cost_bags(Ord, 1, BF, P), flight_cost(Tk), Total is Tk+BF+P.
total_cost(Min) :-
    checked_bag_ids(L),
    findall(T, (choose_two(L,F1,F2), choice_cost(F1,F2,T)), Totals),
    min_list(Totals, Min).
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.