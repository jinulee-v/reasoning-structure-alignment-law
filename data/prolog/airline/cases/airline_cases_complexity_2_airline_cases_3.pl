ticket_price(332).
bag(2,38,22,14,56). bag(3,51,28,25,62). bag(4,35,17,11,70). bag(5,49,28,20,52).
bag(6,47,30,24,56). bag(7,53,34,26,56). bag(8,33,17,13,61). bag(9,39,24,20,52).
bag(10,37,17,9,67). bag(11,36,18,11,65).
checked_bag_list([2,3,4,5,6,7,8,9,10,11]).
oversize_fee(Sum, Fee) :-
    ( Sum =< 62 -> Fee = 0 ; Sum =< 65 -> Fee = 30 ; Sum =< 115 -> Fee = 150 ).
overweight_fee(Weight, Thresh, Fee) :-
    ( Weight =< Thresh -> Fee = 0 ; Weight =< 53 -> Fee = 30 ; Weight =< 70 -> Fee = 100 ).
penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Wt), S is L+W+H, oversize_fee(S,OS), overweight_fee(Wt,50,OW), Pen is max(OS,OW).
bag_fee(1, 0). bag_fee(2, 100). bag_fee(N, 200) :- N >= 3.
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CS, PS) :-
    bag_fee(Idx, Fee), penalty(Bag, charged, Pen), Next is Idx+1,
    cost_bags(Bs, Next, RF, RP), CS is Fee+RF, PS is Pen+RP.
total_cost(T) :- checked_bag_list(L), cost_bags(L,1,F,P), ticket_price(Tk), T is Tk+F+P.
:- total_cost(T), format('Total cost: ~w~n', [T]), halt.