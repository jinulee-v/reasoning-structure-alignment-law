ticket_price(54).
bag(2, 38, 12, 14, 97). bag(3, 42, 24, 16, 53). bag(4, 49, 35, 27, 53).
bag(5, 33, 22, 10, 74). bag(6, 41, 19, 13, 71). bag(7, 37, 15, 11, 68). bag(8, 51, 32, 31, 51).
checked_bag_list([2, 3, 4, 5, 6, 7, 8]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 200 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Weight), S is L+W+H, oversize_fee(S,OS), overweight_fee(Weight,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Weight), S is L+W+H, oversize_fee(S,OS), overweight_fee(Weight,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(N, 200) :- N >= 3.
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CS, PS) :-
    ( Idx =< 2 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CS is Fee+RF, PS is Pen+RP.
total_bag_cost(BT) :- checked_bag_list(L), cost_bags(L, 1, F, P), BT is F+P.
total_cost(T) :- ticket_price(P), total_bag_cost(B), T is P+B.
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.