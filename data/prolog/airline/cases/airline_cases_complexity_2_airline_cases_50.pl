flight_cost(744).
bag(2,40,25,14,57). bag(3,33,21,10,66). bag(4,38,13,12,52). bag(5,43,20,18,52).
bag(6,52,26,28,52). bag(7,36,16,13,53). bag(8,38,15,12,67). bag(9,39,21,13,51).
bag(10,49,28,28,55). bag(11,48,33,28,68).
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 200 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 100). bag_fee(N, 200) :- N >= 3.
choose_free(List, Free) :- member(Free, List).
ordered_list(Free, Ordered) :-
    checked_bag_ids(All), select(Free, All, Rest), Ordered = [Free|Rest].
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CS, PS) :-
    ( Idx =:= 1 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CS is Fee+RF, PS is Pen+RP.
cost_for_choice(Free, Total) :-
    ordered_list(Free, Ord), cost_bags(Ord, 1, BF, P), flight_cost(Fl), Total is Fl+BF+P.
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T, (choose_free(L,Free), cost_for_choice(Free,T)), Totals),
    min_list(Totals, MinTotal).
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.