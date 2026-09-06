ticket_price(1305).
bag(2,34,17,14,88). bag(3,37,18,10,59). bag(4,52,32,25,79). bag(5,54,32,27,69).
bag(6,49,35,26,65). bag(7,36,19,10,99). bag(8,40,15,15,59). bag(9,38,23,15,66).
bag(10,51,33,25,51). bag(11,50,28,21,83).
checked_bag_list([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 200 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ; Weight =< 100 -> Fee = 450 ).
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,70,OW), Pen is max(OS,OW).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 0). bag_fee(N, 200) :- N >= 3.
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CS, PS) :-
    ( Idx =< 2 -> Type = comp ; Type = charged ),
    bag_fee(Idx, Fee), penalty(Bag, Type, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CS is Fee+RF, PS is Pen+RP.
total_cost(T) :- checked_bag_list(L), cost_bags(L,1,F,P), ticket_price(Tk), T is Tk+F+P.
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.