/* ----------  ROUTE / CABIN RULES NEEDED FOR THIS CASE  ---------- */

/* main_cabin_base_fee(+BagNumber, -Fee)
   BagNumber begins at 1 for the first CHECKED bag                                   */

main_cabin_base_fee(1,35).        /* Canada <--> U.S. first bag                 */
main_cabin_base_fee(2,45).        /* second bag                                 */
main_cabin_base_fee(3,150).       /* third bag                                  */
main_cabin_base_fee(N,200):-      /* 4th-plus bags                              */
    N>=4.

/* overweight_fee(+Weight, -Fee) - route: U.S./Canada (see statutes)               */
overweight_fee(W,0)  :- W =< 50.
overweight_fee(W,30) :- W  > 50, W =< 53.
overweight_fee(W,100):- W > 53 , W =< 70.
overweight_fee(W,200):- W > 70 , W =< 100.
/* (weights above 100 lb are "not accepted", not needed here)                       */

/* oversize_fee(+DimSum, -Fee) - route: U.S./Canada (see statutes)                 */
oversize_fee(D,0)   :- D =< 62.
oversize_fee(D,30)  :- D > 62, D =< 65.
oversize_fee(D,200) :- D > 65, D =< 115.
/* (bags above 115 in are "not accepted", not needed here)                          */

/* choose the higher of the two surcharges                                          */
surcharge(Weight,DimSum,Fee):-
    overweight_fee(Weight,WFee),
    oversize_fee(DimSum,OFee),
    (WFee >= OFee -> Fee = WFee ; Fee = OFee).


/* ----------  FACTS FOR JOHN'S TRIP  ---------- */

ticket_price(131).

/* item(Index, Length, Width, Height, Weight).  (in inches / pounds)                */
item(1,21,12, 6, 11).
item(2,36,18,10, 69).
item(3,43,29,17, 52).
item(4,38,21,19, 88).
item(5,47,27,24, 51).
item(6,38,11,14, 73).
item(7,39,16,11, 53).
item(8,38,16,10, 53).

/* carry-on test (1 personal item allowed but none of the bags fits;
   1 carry-on allowed if =<22*14*9 in)                                                 */
carryon_candidate(I):-
    item(I,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* take the first candidate (smallest index) as the free carry-on                   */
carryon(I):-
    carryon_candidate(I),
    \+ (carryon_candidate(J), J < I).

/* every other item is a checked bag                                                */
checked(I):-
    item(I,_,_,_,_),
    \+ carryon(I).

/* position of each checked bag in the sequence (to know 1st, 2nd, ...)               */
bag_number(I,N):-
    findall(X,checked(X),List),
    nth1(N,List,I).


/* ----------  COST CALCULATIONS  ---------- */

bag_cost(I,Cost):-
    item(I,L,W,H,Weight),
    DimSum is L+W+H,
    bag_number(I,N),
    main_cabin_base_fee(N,Base),
    surcharge(Weight,DimSum,Surch),
    Cost is Base + Surch.

/* total for all checked bags                                                       */
total_bags_cost(Total):-
    findall(C,(checked(I),bag_cost(I,C)),List),
    sum_list(List,Total).

/* overall total                                                                    */
total_cost(Total):-
    ticket_price(Ticket),
    total_bags_cost(Bags),
    Total is Ticket + Bags.


/* ----------  ANSWER  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.