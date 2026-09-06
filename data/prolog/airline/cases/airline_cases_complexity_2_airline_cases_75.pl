flight_cost(598).
bag(2,41,22,21,63). bag(3,47,23,20,96). bag(4,36,20,9,53). bag(5,48,27,23,69).
bag(6,38,13,12,100). bag(7,38,11,14,53). bag(8,36,18,11,68). bag(9,41,29,18,90).
bag(10,49,34,29,91). bag(11,45,27,20,73).
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 450 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(N, 200) :- N >= 3.
choose_two(List, F1, F2) :- append(_, [F1|Tail], List), member(F2, Tail), F1 @< F2.
ordered_list(F1, F2, Ordered) :-
    checked_bag_ids(All), select(F1, All, R1), select(F2, R1, R), Ordered = [F1,F2|R].
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, BFS, PS) :-
    ( Idx =< 2 -> Type = comp ; Type = charged ),
    bag_fee(Idx, BF), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, BR, PR), BFS is BF+BR, PS is Pen+PR.
cost_for_choice(F1, F2, Total) :-
    ordered_list(F1, F2, L), cost_bags(L, 1, BF, P), flight_cost(Fl), Total is Fl+BF+P.
total_cost(MinTotal) :-
    checked_bag_ids(List),
    findall(T, (choose_two(List,F1,F2), cost_for_choice(F1,F2,T)), Totals),
    min_list(Totals, MinTotal).
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.