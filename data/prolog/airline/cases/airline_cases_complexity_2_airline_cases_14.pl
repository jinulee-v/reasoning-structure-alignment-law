ticket_price(176).
bag(2,35,16,14,78). bag(3,36,22,13,51). bag(4,35,17,13,55). bag(5,34,21,10,72).
bag(6,47,29,26,53). bag(7,33,18,14,71). bag(8,41,23,15,53). bag(9,55,31,29,67).
bag(10,44,22,22,93). bag(11,33,21,9,80).
checked_bag_list([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 150 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 200 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,W2), S is L+W+H, oversize_fee(S,OS), overweight_fee(W2,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,W2), S is L+W+H, oversize_fee(S,OS), overweight_fee(W2,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(N, 200) :- N >= 3.
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CS, PS) :-
    ( Idx =< 2 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CS is Fee+RF, PS is Pen+RP.
total_cost(T) :- checked_bag_list(L), cost_bags(L,1,F,P), ticket_price(Tk), T is Tk+F+P.
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.