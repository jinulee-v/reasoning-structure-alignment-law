/* ----------  Statutory rules (subset needed for this case)  ---------- */

/* flight region */
within_us(denver,seattle).

/* passenger class */
passenger_class(main_plus).

/* free-bag allowance for Main Plus */
free_checked_bags(1).

/* checked-bag base fees (within U.S.) */
base_fee(1,40).
base_fee(2,45).
base_fee(3,150).
base_fee(N,200):- N>=4.

/* overweight fees (within U.S.) */
overweight_fee(W,30):- W>50, W=<53.          /* 51-53 lbs */
overweight_fee(W,100):- W>53, W=<70.         /* 54-70 lbs - not used here */
overweight_fee(W,200):- W>70, W=<100.        /* 71-100 lbs */
overweight_fee(W,0  ):- W=<50.               /* within allowance */

/* oversize fees (within U.S.) : total dimensions */
oversize_fee(D,30 ):- D>62, D=<65.
oversize_fee(D,200):- D>65, D=<115.
oversize_fee(D,0  ):- D=<62.

/* choose the larger of the 2 special fees */
special_fee(BagID,Fee):-
    bag(BagID,_,_,_,W),
    dimension_total(BagID,D),
    overweight_fee(W,OWF),
    oversize_fee(D,OSF),
    (OWF>=OSF -> Fee=OWF ; Fee=OSF).

/* carry-on limits */
carry_on_ok(L,W,H):- L=<22, W=<14, H=<9.

/* ----------  Facts for this passenger  ---------- */

ticket_cost(215).

/* bag(ID, Length, Width, Height, Weight) */
bag(1,22,12,8,8).
bag(2,37,17,9,51).
bag(3,34,20,11,53).
bag(4,38,15,10,100).
bag(5,41,21,12,78).

/* ----------  Auxiliary predicates  ---------- */

/* total outside dimensions */
dimension_total(ID,Total):-
    bag(ID,L,W,H,_),
    Total is L+W+H.

/* determine which bags must be checked and assign their position order */
checked_bag_position(ID,Pos):-
    findall(B,
            (bag(B,L,W,H,_), \+ carry_on_ok(L,W,H)),
            CheckedList),
    nth1(Pos,CheckedList,ID).

/* base fee for each checked bag taking account of free allowance */
bag_base_fee(ID,FeeDue):-
    checked_bag_position(ID,Pos),
    base_fee(Pos,Base),
    free_checked_bags(Free),
    (Pos =< Free -> FeeDue = 0 ; FeeDue = Base).

/* total of all checked-bag base fees */
total_base_fees(Sum):-
    findall(F, (bag(ID,_,_,_,_), checked_bag_position(ID,_), bag_base_fee(ID,F)), Fs),
    sumlist(Fs,Sum).

/* total of all special (oversize / overweight) fees */
total_special_fees(Sum):-
    findall(F, (bag(ID,_,_,_,_), checked_bag_position(ID,_), special_fee(ID,F)), Fs),
    sumlist(Fs,Sum).

/* ----------  Final computation  ---------- */
total_cost(Total):-
    ticket_cost(Ticket),
    total_base_fees(Base),
    total_special_fees(Special),
    Total is Ticket + Base + Special.

/* ----------  Query & output  ---------- */
:- total_cost(T), format('Total cost: ~w~n',[T]).
:- halt.