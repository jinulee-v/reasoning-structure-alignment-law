flight_cost(1303).
bag(2,34,15,14,55). bag(3,37,18,17,81). bag(4,40,24,14,64). bag(5,38,18,9,69).
bag(6,37,16,12,52). bag(7,35,15,14,80). bag(8,50,29,28,76). bag(9,44,28,18,51).
bag(10,46,28,18,52). bag(11,38,20,15,87).
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
choose_two(List, F1, F2) :- append(_, [F1|Tail], List), member(F2, Tail).
ordered_list(F1, F2, Ordered) :-
    checked_bag_ids(All), select(F1, All, Tmp), select(F2, Tmp, Rest), Ordered = [F1,F2|Rest].
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, FS, PS) :-
    ( Idx =< 2 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), FS is Fee+RF, PS is Pen+RP.
cost_for_choice(F1, F2, Total) :-
    ordered_list(F1, F2, Ord), cost_bags(Ord, 1, BF, P), flight_cost(Fl), Total is Fl+BF+P.
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T, (choose_two(L,F1,F2), cost_for_choice(F1,F2,T)), Totals),
    min_list(Totals, MinTotal).
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.