flight_cost(503).
bag(2, 33, 18, 14, 69).
bag(3, 38, 19, 18, 71).
bag(4, 37, 14, 12, 60).
bag(5, 33, 16, 14, 58).
checked_bag_ids([2, 3, 4, 5]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62  -> Fee = 0 ; Sum =< 65  -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 450 ).
penalty(BagId, comp, Pen) :-
    bag(BagId, L, W, H, Weight), S is L+W+H, oversize_fee(S, OS), overweight_fee(Weight, 70, OW), Pen is max(OS, OW).
penalty(BagId, charged, Pen) :-
    bag(BagId, L, W, H, Weight), S is L+W+H, oversize_fee(S, OS), overweight_fee(Weight, 50, OW), Pen is max(OS, OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(3, 0). bag_fee(N, 200) :- N >= 4.
choose_three(List, F1, F2, F3) :-
    append(_, [F1|T1], List), append(_, [F2|T2], T1), member(F3, T2).
ordered_list(F1, F2, F3, Ordered) :-
    checked_bag_ids(All), select(F1, All, R1), select(F2, R1, R2), select(F3, R2, Rest),
    Ordered = [F1, F2, F3 | Rest].
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CostSum, PenSum) :-
    ( Idx =< 3 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CostSum is Fee+RF, PenSum is Pen+RP.
cost_for_choice(F1, F2, F3, Total) :-
    ordered_list(F1, F2, F3, Ordered), cost_bags(Ordered, 1, BF, P), flight_cost(Fl), Total is Fl+BF+P.
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T, (choose_three(L,F1,F2,F3), cost_for_choice(F1,F2,F3,T)), Totals),
    min_list(Totals, MinTotal).
:- total_cost(Total), format('Total cost: ~w~n', [Total]), halt.