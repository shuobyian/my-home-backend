import {
  Column,
  CreateDateColumn,
  Entity,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity('item', { schema: 'public' })
export class Item {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @CreateDateColumn({
    type: 'timestamp with time zone',
    name: 'createdAt',
    default: () => 'CURRENT_TIMESTAMP',
  })
  createdAt: string;

  @UpdateDateColumn({
    type: 'timestamp with time zone',
    name: 'updatedAt',
    nullable: true,
  })
  updatedAt: string | null;

  @Column('varchar', { unique: true, name: 'name' })
  name: string;

  @Column('integer', { name: 'level' })
  level: number;

  @Column('integer', { name: 'craftingPrice' })
  craftingPrice: number;

  @Column('varchar', { name: 'material1' })
  material1: string;

  @Column('integer', { name: 'base1' })
  base1: number;

  @Column('float', { name: 'count1' })
  count1: number;

  @Column('varchar', { name: 'material2', nullable: true })
  material2: string | null;

  @Column('integer', { name: 'base2', nullable: true })
  base2: number | null;

  @Column('float', { name: 'count2', nullable: true })
  count2: number | null;

  @Column('varchar', { name: 'material3', nullable: true })
  material3: string | null;

  @Column('integer', { name: 'base3', nullable: true })
  base3: number | null;

  @Column('float', { name: 'count3', nullable: true })
  count3: number | null;

  @Column('varchar', { name: 'material4', nullable: true })
  material4: string | null;

  @Column('integer', { name: 'base4', nullable: true })
  base4: number | null;

  @Column('float', { name: 'count4', nullable: true })
  count4: number | null;

  @Column('varchar', { name: 'material5', nullable: true })
  material5: string | null;

  @Column('float', { name: 'base5', nullable: true })
  base5: number | null;

  @Column('integer', { name: 'count5', nullable: true })
  count5: number | null;
}
