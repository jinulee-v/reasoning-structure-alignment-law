/* ----------  Statutory rules that apply to this case ---------- */

/* ticket price */
flight_ticket(1333).

/* --------- base checked-bag fee for Basic Economy
              (route: To / From Hong Kong, i.e. "India / China /
              Japan / South Korea / Hong Kong / Australia / NZ")  ----- */

base_fee(1,75).            /* 1st checked bag   */
base_fee(2,100).           /* 2nd checked bag   */
base_fee(N,200) :-         /* 3rd bag and every bag after that */
    integer(N), N>2.

/* --------------  oversize fees (in inches, L+W+H) --------------- */
oversize_fee(Size,30)  :- Size>62 , Size=<65.
oversize_fee(Size,200) :- Size>65 , Size=<115.
oversize_fee(Size,0)   :- Size=<62.

/* --------------  overweight fees (in pounds) -------------------- */
overweight_fee(W,450) :- W>70 , W=<100.         /* 70 - 100 lbs */
overweight_fee(W,100) :- W>53 , W=<70.          /* 53 - 70  lbs */
overweight_fee(W,30)  :- W>50 , W=<53.          /* 50 - 53  lbs */
overweight_fee(W,0)   :- W=<50.

/* For any bag, the extra charge is the higher of over-size vs over-weight */
extra_fee(Size,Weight,Fee) :-
    oversize_fee(Size,O),
    overweight_fee(Weight,W),
    (O>W -> Fee=O ; Fee=W).

/* ---------------- The bags Linda is checking ------------------- */
/* bag(Number, Length, Width, Height, Weight) */

bag(1,35,16,12,98).
bag(2,36,15,12,63).
bag(3,35,21,9, 99).
bag(4,42,22,17,53).
bag(5,34,21,11,52).
bag(6,45,24,16,77).
bag(7,36,13,14,97).

/* --------------  Cost of every individual checked bag ---------- */
bag_cost(Num,Cost) :-
    bag(Num,L,W,H,Weight),
    Size is L+W+H,
    extra_fee(Size,Weight,Extra),
    base_fee(Num,Base),
    Cost is Base + Extra.

/* -------------- Sum helpers ------------------------------------ */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S1), S is H+S1.

/* -------------- Total of all checked bags ---------------------- */
bag_total(Total) :-
    findall(C,bag_cost(_,C),Cs),
    sum_list(Cs,Total).

/* -------------------- Grand total ------------------------------ */
total_cost(Total) :-
    flight_ticket(Tkt),
    bag_total(Bags),
    Total is Tkt + Bags.

/* -------------------  Output query ----------------------------- */
:- total_cost(Total),
   format('Total cost: ~w~n',[Total]).
:- halt.